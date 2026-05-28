"use client";

import { useEffect, useRef } from "react";

/* Characters used in the rain — binary + hex + hacker symbols */
const CHARS =
  "01010110111001000010111101010011" +
  "0123456789ABCDEF" +
  "!@#$%^&*<>{}[]|\\;:?/" +
  "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉ" +  /* katakana */
  "01" ; /* weight binary heavier */

const FONT_SIZE = 14;
const RAIN_SPEED_MIN = 1;
const RAIN_SPEED_MAX = 3;
/* Every N frames a column resets to top */
const RESET_CHANCE = 0.008;

type Column = {
  x: number;
  y: number;
  speed: number;
  length: number;   /* visible trail length in chars */
  chars: string[];  /* current character for each cell in the trail */
};

function randomChar() {
  return CHARS[Math.floor(Math.random() * CHARS.length)];
}

function randomSpeed() {
  return RAIN_SPEED_MIN + Math.random() * (RAIN_SPEED_MAX - RAIN_SPEED_MIN);
}

export function MatrixRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let cols: Column[] = [];

    function init() {
      if (!canvas) return;
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;

      const numCols = Math.floor(canvas.width / FONT_SIZE);
      cols = [];

      for (let i = 0; i < numCols; i++) {
        const trailLen = 8 + Math.floor(Math.random() * 20);
        cols.push({
          x:      i * FONT_SIZE,
          y:      -Math.random() * canvas.height,  /* stagger starts */
          speed:  randomSpeed(),
          length: trailLen,
          chars:  Array.from({ length: trailLen }, randomChar),
        });
      }
    }

    function draw() {
      if (!canvas || !ctx) return;

      /* Semi-transparent black wash — creates the fade trail */
      ctx.fillStyle = "rgba(0, 0, 0, 0.06)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = `${FONT_SIZE}px "IBM Plex Mono", monospace`;

      for (const col of cols) {
        /* Randomly mutate one character in the trail each frame */
        const mutIdx = Math.floor(Math.random() * col.chars.length);
        col.chars[mutIdx] = randomChar();

        for (let j = 0; j < col.chars.length; j++) {
          const cellY = col.y - j * FONT_SIZE;
          if (cellY < -FONT_SIZE || cellY > canvas.height + FONT_SIZE) continue;

          if (j === 0) {
            /* Head: brightest white-green with glow */
            ctx.fillStyle = "#CCFFCC";
            ctx.shadowColor = "#00FF41";
            ctx.shadowBlur  = 10;
          } else {
            /* Trail: fade from bright to dark green */
            const alpha = Math.max(0, 1 - j / col.chars.length);
            const g = Math.floor(80 + 175 * alpha);   /* 80–255 */
            ctx.fillStyle = `rgb(0, ${g}, ${Math.floor(g * 0.25)})`;
            ctx.shadowBlur = j < 3 ? 6 : 0;
          }

          ctx.fillText(col.chars[j], col.x, cellY);
        }

        /* Advance column */
        col.y += col.speed;

        /* Reset when fully off-screen or by random chance */
        if (col.y - col.length * FONT_SIZE > canvas.height || Math.random() < RESET_CHANCE) {
          col.y     = -FONT_SIZE * 2;
          col.speed = randomSpeed();
          col.chars = Array.from({ length: col.length }, randomChar);
        }
      }

      /* Reset shadow so it doesn't bleed */
      ctx.shadowBlur  = 0;
      ctx.shadowColor = "transparent";

      animId = requestAnimationFrame(draw);
    }

    init();
    draw();

    const onResize = () => { init(); };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        opacity: 0.45,   /* subtle — readable content above */
      }}
    />
  );
}
