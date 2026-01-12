
import React from 'react';
import { Check } from 'lucide-react';
import {
  seedlingIcon,
  intertwinedRootsIcon,
  zenStonesIcon,
  organicGearsIcon,
  mushroomStumpIcon
} from '../assets/icons';

interface StepIndicatorProps {
  currentStep: number;
}

const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep }) => {
  const steps = [
    { label: "意图", icon: seedlingIcon },
    { label: "研究", icon: intertwinedRootsIcon },
    { label: "大纲", icon: zenStonesIcon },
    { label: "风格", icon: organicGearsIcon },
    { label: "生成", icon: mushroomStumpIcon },
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
                className={`w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full border-2 transition-all duration-500 z-10 overflow-hidden p-1.5
                  ${isActive ? 'bg-[#5D7052]/10 border-[#5D7052] scale-110 shadow-lg' :
                    isCompleted ? 'bg-[#C18C5D]/10 border-[#C18C5D]' :
                      'bg-[#FDFCF8] border-[#DED8CF]'}`}
              >
                {isCompleted ? (
                  <Check size={20} className="text-[#C18C5D]" />
                ) : (
                  <img src={step.icon} alt={step.label} className="w-full h-full object-contain" />
                )}
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
