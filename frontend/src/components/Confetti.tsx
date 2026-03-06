import React, { useEffect, useState, useRef } from 'react';

interface ConfettiPiece {
    id: number;
    x: number;
    y: number;
    size: number;
    color: string;
    rotation: number;
    speedX: number;
    speedY: number;
    rotationSpeed: number;
}

interface ConfettiProps {
    isActive: boolean;
    duration?: number;
    pieceCount?: number;
}

const COLORS = ['#5D7052', '#C18C5D', '#E6DCCD', '#A85448', '#78786C', '#FFD700', '#FF6B6B', '#4ECDC4'];

const Confetti: React.FC<ConfettiProps> = ({
    isActive,
    duration = 4000,
    pieceCount = 100,
}) => {
    const [pieces, setPieces] = useState<ConfettiPiece[]>([]);
    const [isVisible, setIsVisible] = useState(false);
    const animationRef = useRef<number | null>(null);
    const startTimeRef = useRef<number | null>(null);

    useEffect(() => {
        if (isActive) {
            // 生成彩带碎片
            const newPieces: ConfettiPiece[] = [];
            for (let i = 0; i < pieceCount; i++) {
                newPieces.push({
                    id: i,
                    x: Math.random() * 100,
                    y: -10 - Math.random() * 20,
                    size: 6 + Math.random() * 8,
                    color: COLORS[Math.floor(Math.random() * COLORS.length)],
                    rotation: Math.random() * 360,
                    speedX: (Math.random() - 0.5) * 3,
                    speedY: 2 + Math.random() * 3,
                    rotationSpeed: (Math.random() - 0.5) * 10,
                });
            }
            setPieces(newPieces);
            setIsVisible(true);
            startTimeRef.current = Date.now();

            // 开始动画
            const animate = () => {
                const elapsed = Date.now() - (startTimeRef.current || 0);
                if (elapsed < duration) {
                    setPieces(prev => prev.map(p => ({
                        ...p,
                        x: p.x + p.speedX * 0.1,
                        y: p.y + p.speedY * 0.1,
                        rotation: p.rotation + p.rotationSpeed,
                        speedY: p.speedY + 0.02, // 重力
                    })));
                    animationRef.current = requestAnimationFrame(animate);
                } else {
                    setIsVisible(false);
                }
            };
            animationRef.current = requestAnimationFrame(animate);
        }

        return () => {
            if (animationRef.current !== null) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [isActive, duration, pieceCount]);

    if (!isVisible) return null;

    return (
        <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
            {pieces.map(piece => (
                <div
                    key={piece.id}
                    className="absolute"
                    style={{
                        left: `${piece.x}%`,
                        top: `${piece.y}%`,
                        width: piece.size,
                        height: piece.size * 0.6,
                        backgroundColor: piece.color,
                        transform: `rotate(${piece.rotation}deg)`,
                        borderRadius: '2px',
                        opacity: Math.max(0, 1 - piece.y / 120),
                    }}
                />
            ))}
        </div>
    );
};

export default Confetti;
