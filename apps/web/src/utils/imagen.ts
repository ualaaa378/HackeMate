const ANCHO_MAX = 1200;

/** Reduce la foto a 1200 px de ancho como mucho y la pasa a WebP (o JPEG si el navegador no sabe).
 *  Devuelve una data URL que va en `imagen_url` hasta que la API tenga subida de archivos. */
export async function comprimirImagen(archivo: Blob, anchoMax = ANCHO_MAX): Promise<string> {
  const bmp = await createImageBitmap(archivo);
  const escala = Math.min(1, anchoMax / bmp.width);
  const w = Math.round(bmp.width * escala);
  const h = Math.round(bmp.height * escala);
  const lienzo = document.createElement('canvas');
  lienzo.width = w;
  lienzo.height = h;
  const ctx = lienzo.getContext('2d');
  if (!ctx) throw new Error('sin_canvas');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close();
  const webp = lienzo.toDataURL('image/webp', 0.72);
  return webp.startsWith('data:image/webp') ? webp : lienzo.toDataURL('image/jpeg', 0.75);
}
