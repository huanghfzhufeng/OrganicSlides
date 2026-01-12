
import React from 'react';
import { Sparkles, Globe, Layout, Palette, Feather, Check } from 'lucide-react';

interface StepIndicatorProps {
  currentStep: number;
}

const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep }) => {
  const totalSteps = 5;
  const steps = [
    { label: "意图", icon: Sparkles },
    { label: "研究", icon: Globe },
    { label: "大纲", icon: Layout },
    { label: "风格", icon: Palette },
    { label: "生成", icon: Feather },
  ];

  return (
    <div className="flex items-center justify-center mb-12 relative z-10">
      {steps.map((step, idx) => {
        const isActive = idx === currentStep;
        const isCompleted = idx < currentStep;

        return (
          <div key={idx} className="flex items-center">
            <div className={`flex flex-col items-center gap-2 relative ${idx !== steps.length - 1 ? 'w-24 md:w-32' : ''}`}>
              <div
                className={`w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full border-2 transition-all duration-500 z-10
                  ${isActive ? 'bg-[#5D7052] border-[#5D7052] text-white scale-110 shadow-lg' :
                    isCompleted ? 'bg-[#C18C5D] border-[#C18C5D] text-white' :
                      'bg-[#FDFCF8] border-[#DED8CF] text-[#DED8CF]'}`}
              >
                {isCompleted ? <Check size={20} /> : <step.icon size={20} />}
              </div>
              <span className={`absolute top-14 text-xs font-bold tracking-wider transition-colors duration-300
                ${isActive ? 'text-[#5D7052]' : isCompleted ? 'text-[#C18C5D]' : 'text-[#DED8CF]'}`}>
                {step.label}
              </span>

              {/* Connector Line */}
              {idx !== steps.length - 1 && (
                <div className="absolute top-5 left-[50%] w-full h-0.5 bg-[#DED8CF] -z-0">
                  <div
                    className="h-full bg-[#C18C5D] transition-all duration-700 ease-out"
                    style={{ width: isCompleted ? '100%' : '0%' }}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default StepIndicator;
