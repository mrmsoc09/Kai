import React, { useEffect, useState } from 'react';
import confetti from 'canvas-confetti';

/**
 * K1 PayoutEvent Component (Stage 18).
 * Triggers the 'Lazer Show' / Confetti animation when a payout or verified PoC is detected.
 */
export const PayoutEvent: React.FC<{ active: boolean; type: 'poc' | 'bounty' }> = ({ active, type }) => {
  useEffect(() => {
    if (active) {
      const colors = type === 'poc' ? ['#A6E22E', '#FFD700'] : ['#FFD700', '#FFFFFF'];
      
      // Initial burst
      confetti({
        particleCount: 150,
        spread: 70,
        origin: { y: 0.6 },
        colors: colors
      });

      // Lateral lasers (simulated with streaks)
      const interval = setInterval(() => {
        confetti({
          particleCount: 2,
          angle: 60,
          spread: 55,
          origin: { x: 0 },
          colors: colors
        });
        confetti({
          particleCount: 2,
          angle: 120,
          spread: 55,
          origin: { x: 1 },
          colors: colors
        });
      }, 50);

      return () => clearInterval(interval);
    }
  }, [active, type]);

  if (!active) return null;

  return (
    <div className="fixed inset-0 z-[100] pointer-events-none flex items-center justify-center bg-gold/5 animate-pulse">
      <div className="text-center p-8 bg-black/80 border-4 border-gold rounded-3xl shadow-[0_0_50px_rgba(255,215,0,0.5)]">
        <h1 className="text-6xl font-black text-gold mb-4 italic tracking-tighter">
          {type === 'poc' ? 'VULNERABILITY VERIFIED' : 'BOUNTY CONFIRMED'}
        </h1>
        <p className="text-xl text-white font-mono uppercase tracking-[0.5em]">
          Target Compromised • Sovereignty Achieved
        </p>
      </div>
    </div>
  );
};
