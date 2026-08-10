export function isBarcodeScannerSupported() {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
}
