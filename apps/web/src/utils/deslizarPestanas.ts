import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const UMBRAL_PX = 70;

/** Elementos que ya usan el gesto horizontal (mapa, carruseles, campos de texto, rangos…). */
function usaGestoHorizontal(objetivo: EventTarget | null): boolean {
  let el = objetivo instanceof Element ? objetivo : null;
  while (el && el !== document.body) {
    if (
      el.matches('.leaflet-container, input, textarea, ion-range, ion-segment, ion-modal, ion-action-sheet, ion-alert')
    )
      return true;
    if (el instanceof HTMLElement && el.scrollWidth > el.clientWidth + 4) {
      const ox = getComputedStyle(el).overflowX;
      if (ox === 'auto' || ox === 'scroll') return true;
    }
    el = el.parentElement;
  }
  return false;
}

/** Cambiar de pestaña deslizando el dedo a izquierda o derecha (en el APK). */
export function useDeslizarPestanas(rutas: string[], pathname: string, activo: boolean): void {
  const navigate = useNavigate();
  useEffect(() => {
    const actual = rutas.indexOf(pathname);
    if (!activo || actual < 0) return;
    let inicio: { x: number; y: number; t: number } | null = null;
    const alEmpezar = (e: TouchEvent) => {
      const dedo = e.touches[0];
      inicio =
        e.touches.length === 1 && !usaGestoHorizontal(e.target)
          ? { x: dedo.clientX, y: dedo.clientY, t: Date.now() }
          : null;
    };
    const alTerminar = (e: TouchEvent) => {
      if (!inicio) return;
      const dedo = e.changedTouches[0];
      const dx = dedo.clientX - inicio.x;
      const dy = dedo.clientY - inicio.y;
      const rapido = Date.now() - inicio.t < 700;
      inicio = null;
      if (!rapido || Math.abs(dx) < UMBRAL_PX || Math.abs(dx) < Math.abs(dy) * 1.8) return;
      const destino = actual + (dx < 0 ? 1 : -1);
      if (destino >= 0 && destino < rutas.length) navigate(rutas[destino]);
    };
    document.addEventListener('touchstart', alEmpezar, { passive: true });
    document.addEventListener('touchend', alTerminar, { passive: true });
    return () => {
      document.removeEventListener('touchstart', alEmpezar);
      document.removeEventListener('touchend', alTerminar);
    };
  }, [rutas, pathname, activo, navigate]);
}
