import React from 'react';

interface SkeletonProps {
    className?: string;
    variant?: 'text' | 'circular' | 'rectangular';
    width?: string | number;
    height?: string | number;
    lines?: number;
}

const Skeleton: React.FC<SkeletonProps> = ({
    className = '',
    variant = 'rectangular',
    width,
    height,
    lines = 1,
}) => {
    const baseClass = 'animate-pulse bg-gradient-to-r from-[#E6DCCD] via-[#F0EBE5] to-[#E6DCCD] bg-[length:200%_100%] animate-[shimmer_1.5s_ease-in-out_infinite]';

    const variantClasses = {
        text: 'rounded-md h-4',
        circular: 'rounded-full',
        rectangular: 'rounded-xl',
    };

    const style: React.CSSProperties = {
        width: width || '100%',
        height: height || (variant === 'text' ? '1rem' : variant === 'circular' ? width : '100%'),
    };

    if (lines > 1 && variant === 'text') {
        return (
            <div className={`space-y-2 ${className}`}>
                {Array.from({ length: lines }).map((_, i) => (
                    <div
                        key={i}
                        className={`${baseClass} ${variantClasses[variant]}`}
                        style={{
                            ...style,
                            width: i === lines - 1 ? '60%' : '100%',
                        }}
                    />
                ))}
            </div>
        );
    }

    return (
        <div
            className={`${baseClass} ${variantClasses[variant]} ${className}`}
            style={style}
        />
    );
};

const GENERATION_SKELETON_WIDTHS = ['74%', '82%', '76%', '88%'] as const;

// 研究进度骨架屏
export const ResearchSkeleton: React.FC = () => (
    <div className="space-y-4">
        {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white p-4 rounded-xl border border-[#DED8CF] flex items-center gap-4">
                <Skeleton variant="circular" width={40} height={40} />
                <div className="flex-1">
                    <Skeleton variant="text" width="30%" className="mb-2" />
                    <Skeleton variant="text" width="80%" />
                </div>
                <Skeleton variant="rectangular" width={60} height={24} className="rounded-full" />
            </div>
        ))}
    </div>
);

// 生成结果骨架屏
export const GenerationSkeleton: React.FC = () => (
    <div className="space-y-4">
        {GENERATION_SKELETON_WIDTHS.map((width, index) => (
            <div key={index} className="flex items-start gap-3">
                <Skeleton variant="circular" width={24} height={24} />
                <div className="flex-1">
                    <Skeleton variant="text" width="20%" className="mb-1" />
                    <Skeleton variant="text" width={width} />
                </div>
            </div>
        ))}
    </div>
);
