
import React from 'react';
import { type LucideIcon } from 'lucide-react';

interface BlobButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline' | 'white';
  onClick?: () => void;
  className?: string;
  icon?: LucideIcon;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

const BlobButton: React.FC<BlobButtonProps> = ({
  children,
  variant = 'primary',
  onClick,
  className = '',
  icon: Icon,
  disabled,
  type = 'button'
}) => {
  const baseStyle = "relative overflow-hidden transition-all duration-500 ease-out transform hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2 font-bold tracking-wide py-3 px-8 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed";

  const variants = {
    primary: "bg-[#5D7052] text-[#F3F4F1] hover:shadow-[0_6px_24px_-4px_rgba(93,112,82,0.35)]",
    secondary: "bg-[#C18C5D] text-white hover:shadow-[0_6px_24px_-4px_rgba(193,140,93,0.3)]",
    ghost: "bg-transparent text-[#5D7052] hover:bg-[#5D7052]/10",
    outline: "border-2 border-[#C18C5D] text-[#C18C5D] bg-transparent hover:bg-[#C18C5D]/5",
    white: "bg-white/80 text-[#2C2C24] hover:bg-white shadow-sm"
  };

  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${baseStyle} ${variants[variant]} rounded-full ${className}`}>
      {Icon && <Icon size={18} strokeWidth={2.5} />}
      <span className="font-nunito">{children}</span>
    </button>
  );
};

export default BlobButton;
