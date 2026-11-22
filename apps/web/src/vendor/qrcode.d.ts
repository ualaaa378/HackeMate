interface CodigoQr {
  addData(datos: string): void;
  make(): void;
  getModuleCount(): number;
  isDark(fila: number, columna: number): boolean;
}
declare const qrcode: (tipo: number, correccion: 'L' | 'M' | 'Q' | 'H') => CodigoQr;
export default qrcode;
