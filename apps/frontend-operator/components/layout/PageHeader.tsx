type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div
      style={{
        marginBottom: "1rem",
        paddingBottom: "0.75rem",
        borderBottom: "1px solid #001a00",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "0.75rem",
      }}
    >
      <div>
        {/* Breadcrumb-style prefix */}
        <p
          style={{
            fontSize: "0.6rem",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "#003300",
            fontFamily: "IBM Plex Mono, monospace",
            marginBottom: "2px",
          }}
        >
          {"// KAI OPERATOR ▸"}
        </p>
        <h2
          style={{
            fontSize: "1.1rem",
            fontWeight: 700,
            color: "#00FF41",
            fontFamily: "IBM Plex Mono, monospace",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            textShadow: "0 0 8px rgba(0,255,65,0.4)",
          }}
        >
          <span style={{ color: "#007A1E", marginRight: "0.4em" }}>›</span>
          {title}
          <span
            style={{
              display: "inline-block",
              width: 8,
              marginLeft: 4,
              animation: "blink 1s step-end infinite",
              color: "#00FF41",
            }}
          >
            _
          </span>
        </h2>
        {description ? (
          <p
            style={{
              marginTop: "3px",
              fontSize: "0.7rem",
              color: "#007A1E",
              fontFamily: "IBM Plex Mono, monospace",
              letterSpacing: "0.04em",
            }}
          >
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>{actions}</div> : null}
    </div>
  );
}
