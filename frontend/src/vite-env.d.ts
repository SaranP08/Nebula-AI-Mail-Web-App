/// <reference types="vite/client" />

// CSS Module type declarations — Vite handles these at runtime but tsc needs them
declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}
