import { ImageResponse } from "next/og";

// Imagen que aparece al compartir un enlace de Clipaso en redes o mensajería.
export const alt = "Clipaso · Editor de vídeo para clips verticales";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "linear-gradient(135deg, #0d1608 0%, #16230d 55%, #253a12 100%)",
          color: "white",
          padding: 72,
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <svg width="72" height="72" viewBox="0 0 32 32">
              <rect width="32" height="32" rx="9" fill="#0d1608" stroke="#b6e34a" strokeWidth="0.8" />
              <path d="M11.5 8.8 23.6 16 11.5 23.2Z" fill="#b6e34a" stroke="#b6e34a" strokeWidth="2.4" strokeLinejoin="round" />
              <path d="M8.5 21.5 21.5 9.5" stroke="#0d1608" strokeWidth="2.6" strokeLinecap="round" />
              <circle cx="24.5" cy="8.5" r="1.6" fill="#b6e34a" />
            </svg>
            <span style={{ fontSize: 44, fontWeight: 700 }}>
              Clip<span style={{ color: "#b6e34a" }}>aso</span>
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <span style={{ fontSize: 72, fontWeight: 700, lineHeight: 1.05, maxWidth: 820 }}>
              De un vídeo largo a clips virales
            </span>
            <span style={{ fontSize: 30, color: "rgba(255,255,255,0.72)", maxWidth: 760 }}>
              Edita tu vídeo en clips verticales con subtítulos, listos para publicar.
            </span>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            width: 250,
            height: 444,
            alignSelf: "center",
            borderRadius: 36,
            border: "8px solid #0b0f08",
            background: "linear-gradient(180deg, #475569, #0f172a)",
            alignItems: "flex-end",
            justifyContent: "center",
            paddingBottom: 110,
          }}
        >
          <div style={{ display: "flex", gap: 10, fontSize: 30, fontWeight: 800, color: "white" }}>
            <span>ESTO</span>
            <span style={{ color: "#b6e34a" }}>LO</span>
            <span>CAMBIA</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
