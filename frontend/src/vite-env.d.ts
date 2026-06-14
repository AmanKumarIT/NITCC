/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MAPBOX_ACCESS_TOKEN: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_URL: string
  readonly VITE_ENABLE_SATELLITE_LAYER: string
  readonly VITE_ENABLE_WEATHER_OVERLAY: string
  readonly VITE_ENABLE_DEMO_MODE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
