import React, { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';

/**
 * K1 Stage 18: Sovereign Command Console.
 * Integrates Tmux TUI with a high-fidelity Black & Gold theme.
 * Features the 'Cicada in the Web' background injection.
 */
export const CommandConsole: React.FC = () => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm.js with Monokai/Sovereign Theme
    const term = new Terminal({
      cursorBlink: true,
      theme: {
        background: '#000000',
        foreground: '#A6E22E', // Monokai Green
        cursor: '#FFD700',     // Gold
        black: '#000000',
        red: '#F92672',
        green: '#A6E22E',
        yellow: '#FD971F',
        blue: '#AE81FF',
        magenta: '#F92672',
        cyan: '#66D9EF',
        white: '#F8F8F2',
      },
      fontFamily: 'Fira Code, monospace',
      fontSize: 14,
      allowTransparency: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon());
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;

    // Connect to PTY Bridge WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/terminal`);
    socket.binaryType = 'arraybuffer';
    
    socket.onopen = () => {
      term.writeln('\x1b[1;33m[K1]\x1b[0m Sovereign Link Established. Attaching to Tmux...');
    };

    socket.onmessage = (event) => {
      term.write(new Uint8Array(event.data));
    };

    socket.onclose = () => {
      term.writeln('\n\x1b[1;31m[K1]\x1b[0m Sovereign Link Severed.');
    };

    term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(new TextEncoder().encode(data));
      }
    });

    socketRef.current = socket;

    window.addEventListener('resize', () => fitAddon.fit());

    return () => {
      socket.close();
      term.dispose();
    };
  }, []);

  return (
    <div className="relative w-full h-full bg-black rounded-lg overflow-hidden border border-gray-800 shadow-2xl">
      {/* Cicada Backdrop Injection */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-[0.07] z-0 flex items-center justify-center"
        style={{
          backgroundImage: `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 5L95 95H5L50 5Z" fill="none" stroke="gold" stroke-width="0.5"/><circle cx="50" cy="50" r="40" fill="none" stroke="gold" stroke-width="0.2"/></svg>')`,
          backgroundSize: 'contain',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'center',
        }}
      />
      
      {/* Terminal Viewport */}
      <div ref={terminalRef} className="relative z-10 w-full h-full p-2" />
      
      {/* Ralph Intervention Bubble (Random trigger would be added via state) */}
      <div className="absolute bottom-4 right-4 z-20 bg-gray-900 border border-gold text-xs p-2 rounded-lg text-gold italic animate-bounce hidden">
        "I'm a security researcher!"
      </div>
    </div>
  );
};

export default CommandConsole;
