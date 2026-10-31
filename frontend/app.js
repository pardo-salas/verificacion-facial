// Cliente del frontend: consume la API REST del backend.
const API_URL = (window.APP_CONFIG && window.APP_CONFIG.API_URL) || "http://localhost:8000";
const $ = (id) => document.getElementById(id);

let referencias = [];
let prueba = null;
let flujo = null;

async function revisarSalud() {
  const chip = $("estado-api");
  try {
    const r = await fetch(`${API_URL}/api/v1/health`);
    const datos = await r.json();
    chip.textContent = r.ok ? `API en línea · v${datos.version}` : "API sin modelo";
    chip.className = `chip ${r.ok ? "ok" : "error"}`;
  } catch {
    chip.textContent = "API no disponible";
    chip.className = "chip error";
  }
}

function mostrarMiniaturas(contenedor, archivos) {
  contenedor.innerHTML = "";
  archivos.forEach((archivo) => {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(archivo);
    img.alt = archivo.name;
    contenedor.appendChild(img);
  });
}

function actualizarBoton() {
  $("btn-verificar").disabled = !(referencias.length && prueba);
}

$("referencias").addEventListener("change", (e) => {
  referencias = Array.from(e.target.files).slice(0, 5);
  mostrarMiniaturas($("vista-referencias"), referencias);
  actualizarBoton();
});

$("prueba").addEventListener("change", (e) => {
  prueba = e.target.files[0] || null;
  mostrarMiniaturas($("vista-prueba"), prueba ? [prueba] : []);
  actualizarBoton();
});

$("btn-camara").addEventListener("click", async () => {
  try {
    flujo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    $("video").srcObject = flujo;
    $("camara").classList.remove("oculto");
  } catch {
    alert("No se pudo acceder a la cámara. Revisa los permisos del navegador (requiere localhost o HTTPS).");
  }
});

$("btn-capturar").addEventListener("click", () => {
  const video = $("video");
  const lienzo = $("lienzo");
  lienzo.width = video.videoWidth;
  lienzo.height = video.videoHeight;
  lienzo.getContext("2d").drawImage(video, 0, 0);
  lienzo.toBlob((blob) => {
    prueba = new File([blob], "captura.jpg", { type: "image/jpeg" });
    mostrarMiniaturas($("vista-prueba"), [prueba]);
    actualizarBoton();
  }, "image/jpeg", 0.92);
  flujo.getTracks().forEach((t) => t.stop());
  $("camara").classList.add("oculto");
});

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

function pintarResultado(datos) {
  const caja = $("resultado");
  const cubrebocas = datos.rostro_prueba.posible_cubrebocas;
  caja.className = datos.coincide ? "ok" : "no";
  caja.innerHTML = `
    <h3>${datos.coincide ? "✔ Es la misma persona" : "✘ No coincide"}</h3>
    <div class="metricas">
      <div>Similitud<b>${datos.similitud.toFixed(3)}</b></div>
      <div>Umbral<b>${datos.umbral.toFixed(3)}</b></div>
      <div>Confianza<b>${datos.nivel_confianza}</b></div>
      <div>Cubrebocas en prueba<b>${cubrebocas === null ? "N/D" : cubrebocas ? "Sí" : "No"}</b></div>
      <div>Tiempo<b>${datos.tiempo_ms} ms</b></div>
    </div>
    ${datos.advertencias.length ? `<ul class="avisos">${datos.advertencias.map((a) => `<li>${escapar(a)}</li>`).join("")}</ul>` : ""}`;
}

$("btn-verificar").addEventListener("click", async () => {
  const boton = $("btn-verificar");
  const caja = $("resultado");
  const formulario = new FormData();
  referencias.forEach((archivo) => formulario.append("referencias", archivo));
  formulario.append("prueba", prueba);

  boton.disabled = true;
  boton.textContent = "Verificando…";
  try {
    const r = await fetch(`${API_URL}/api/v1/verificar`, { method: "POST", body: formulario });
    const datos = await r.json();
    if (!r.ok) {
      const detalle = typeof datos.detail === "string" ? datos.detail : JSON.stringify(datos.detail);
      throw new Error(detalle);
    }
    pintarResultado(datos);
  } catch (err) {
    caja.className = "no";
    caja.innerHTML = `<h3>Error</h3><p>${escapar(err.message || "No se pudo conectar con la API.")}</p>`;
  } finally {
    caja.classList.remove("oculto");
    boton.textContent = "Verificar identidad";
    actualizarBoton();
  }
});

revisarSalud();
