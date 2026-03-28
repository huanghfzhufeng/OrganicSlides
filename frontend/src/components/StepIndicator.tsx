import React from 'react';
import { Bot, Check, CheckCircle2, Compass, Lock, Users, Zap } from 'lucide-react';
import {
  seedlingIcon,
  intertwinedRootsIcon,
  zenStonesIcon,
  forestGlobeIcon,
  organicGearsIcon,
  mushroomStumpIcon
} from '../assets/icons';
import type { CollaborationMode, SkillRuntime } from '../api/client';

interface StepIndicatorProps {
  currentStep: number;
  currentStepHint?: string;
  skillRuntime?: SkillRuntime | null;
  collaborationMode?: CollaborationMode;
}

type GateStatus = 'locked' | 'current' | 'complete';

interface CheckpointGate {
  key: string;
  label: string;
  detail: string;
  activeAtStep: number;
}

const MODE_LABEL: Record<CollaborationMode, string> = {
  full_auto: 'Full Auto',
  guided: 'Guided',
  collaborative: 'Collaborative',
};

const MODE_ICON: Record<CollaborationMode, React.ComponentType<{ size?: number; className?: string }>> = {
  full_auto: Zap,
  guided: Compass,
  collaborative: Users,
};

const GATE_LABELS: Record<string, string> = {
  outline_and_blueprint_approval: '内容蓝图确认',
  style_selection: '风格与路径确认',
  assembly_review: '组装前复核',
  final_preview: '最终预览',
  topic_confirmation: '主题确认',
};

const GATE_ACTIVE_STEPS: Record<string, number> = {
  topic_confirmation: 0,
  outline_and_blueprint_approval: 2,
  style_selection: 4,
  assembly_review: 5,
  final_preview: 5,
};

function modeMatchesAudience(audiences: string, mode: CollaborationMode): boolean {
  if (!audiences) return false;
  if (audiences.includes('所有模式')) return true;
  if (mode === 'guided' && audiences.toLowerCase().includes('guided')) return true;
  if (mode === 'collaborative' && audiences.toLowerCase().includes('collaborative')) return true;
  return false;
}

function buildCheckpointGates(
  skillRuntime: SkillRuntime | null | undefined,
  mode: CollaborationMode,
): CheckpointGate[] {
  if (!skillRuntime) {
    return [];
  }

  if (mode === 'full_auto') {
    const modeMeta = skillRuntime.supported_collaboration_modes.find((item) => item.key === mode);
    return [
      {
        key: 'topic_confirmation',
        label: GATE_LABELS.topic_confirmation,
        detail: modeMeta?.checkpoints ?? '确认主题即可',
        activeAtStep: GATE_ACTIVE_STEPS.topic_confirmation,
      },
      {
        key: 'final_preview',
        label: GATE_LABELS.final_preview,
        detail: '系统输出最终结果后再统一预览',
        activeAtStep: GATE_ACTIVE_STEPS.final_preview,
      },
    ];
  }

  const gates: CheckpointGate[] = [];
  for (const step of skillRuntime.runtime_steps) {
    for (const checkpoint of step.checkpoints) {
      if (!modeMatchesAudience(checkpoint.audiences, mode)) {
        continue;
      }
      gates.push({
        key: checkpoint.key,
        label: GATE_LABELS[checkpoint.key] ?? checkpoint.label,
        detail: checkpoint.label,
        activeAtStep: GATE_ACTIVE_STEPS[checkpoint.key] ?? step.number,
      });
    }
  }

  const deduped = new Map<string, CheckpointGate>();
  for (const gate of gates) {
    if (!deduped.has(gate.key)) {
      deduped.set(gate.key, gate);
    }
  }
  return Array.from(deduped.values());
}

function getGateStatus(gate: CheckpointGate, currentStep: number): GateStatus {
  if (currentStep > gate.activeAtStep) return 'complete';
  if (currentStep === gate.activeAtStep) return 'current';
  return 'locked';
}

function getCheckpointIcon(status: GateStatus) {
  if (status === 'complete') return CheckCircle2;
  if (status === 'current') return Check;
  return Lock;
}

const StepIndicator: React.FC<StepIndicatorProps> = ({
  currentStep,
  currentStepHint,
  skillRuntime,
  collaborationMode = 'guided',
}) => {
  const steps = [
    { label: "意图", icon: seedlingIcon, helper: "明确主题" },
    { label: "研究", icon: intertwinedRootsIcon, helper: "收集资料" },
    { label: "大纲", icon: zenStonesIcon, helper: "组织结构" },
    { label: "页策", icon: forestGlobeIcon, helper: "拆成页稿" },
    { label: "风格", icon: organicGearsIcon, helper: "选定视觉" },
    { label: "生成", icon: mushroomStumpIcon, helper: "渲染成片" },
  ];
  const safeStep = Math.min(Math.max(currentStep, 0), steps.length - 1);
  const completedCount = safeStep;
  const activeStep = steps[safeStep];
  const phaseHint = currentStepHint ?? activeStep.helper;
  const gates = buildCheckpointGates(skillRuntime, collaborationMode);
  const ModeIcon = MODE_ICON[collaborationMode];

  return (
    <section className="mb-10 relative z-10">
      <div className="mx-auto max-w-5xl rounded-[32px] border border-[#DED8CF]/80 bg-white/75 px-4 py-5 shadow-[0_30px_70px_-55px_rgba(93,112,82,0.65)] backdrop-blur-sm md:px-8 md:py-6">
        <div className="mb-5 flex flex-col gap-3 px-1 md:flex-row md:items-end md:justify-between">
          <div className="text-left">
            <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-[#A38B74]">
              Creative Flow
            </p>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="font-fraunces text-2xl text-[#2C2C24]">
                当前阶段：{activeStep.label}
              </h2>
              <p className="text-sm text-[#78786C]">
                {phaseHint}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 self-start md:self-auto">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#DED8CF] bg-[#F9F5EE] px-3 py-2 text-xs font-bold text-[#5D7052]">
              <Bot size={14} />
              <span>{skillRuntime?.name ?? 'huashu-slides'}</span>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#DED8CF] bg-[#EEF3EB] px-3 py-2 text-xs font-bold text-[#5D7052]">
              <ModeIcon size={14} />
              <span>{MODE_LABEL[collaborationMode]}</span>
            </div>
            <div className="inline-flex items-center gap-3 rounded-full border border-[#DED8CF] bg-[#F9F5EE] px-4 py-2 text-left">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#A38B74]">
                  已完成
                </p>
                <p className="text-sm font-bold text-[#5D7052]">
                  {completedCount}/{steps.length}
                </p>
              </div>
              <div className="h-8 w-px bg-[#DED8CF]" />
              <p className="max-w-[10rem] text-xs leading-5 text-[#78786C]">
                {safeStep === steps.length - 1 ? '正在输出最终演示文稿' : '流程会自动推进到下一阶段'}
              </p>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto pb-1 no-scrollbar">
          <div className="flex min-w-[720px] items-start justify-between gap-2 px-1 md:min-w-0 md:gap-4">
            {steps.map((step, idx) => {
              const isActive = idx === safeStep;
              const isCompleted = idx < safeStep;
              const connectorFilled = idx < safeStep;

              return (
                <div key={idx} className="relative flex flex-1 flex-col items-center text-center">
                  {idx !== steps.length - 1 && (
                    <div className="absolute left-[calc(50%+2.1rem)] right-[calc(-50%+2.1rem)] top-7 hidden h-[3px] rounded-full bg-[#E8E0D4] md:block">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${
                          connectorFilled
                            ? 'w-full bg-gradient-to-r from-[#C18C5D] via-[#D6A171] to-[#5D7052]'
                            : 'w-0'
                        }`}
                      />
                    </div>
                  )}

                  <div
                    className={`relative mb-3 flex h-14 w-14 items-center justify-center rounded-full border-[3px] transition-all duration-500 md:h-16 md:w-16 ${
                      isActive
                        ? 'border-[#5D7052] bg-[#EEF3EB] shadow-[0_0_0_10px_rgba(93,112,82,0.12),0_16px_30px_-22px_rgba(93,112,82,0.95)]'
                        : isCompleted
                          ? 'border-[#C18C5D] bg-[#FBF3EA] shadow-[0_0_0_8px_rgba(193,140,93,0.1)]'
                          : 'border-[#DED8CF] bg-[#FFFCF7]'
                    }`}
                  >
                    {isActive && (
                      <span className="pulse-ring rounded-full" />
                    )}
                    <img
                      src={step.icon}
                      alt={step.label}
                      className={`h-7 w-7 object-contain transition-all duration-500 md:h-8 md:w-8 ${
                        idx > safeStep ? 'opacity-45 saturate-50' : ''
                      } ${isActive ? 'scale-110' : ''}`}
                    />
                    {isCompleted && (
                      <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full border-2 border-white bg-[#C18C5D] text-white shadow-md">
                        <Check size={13} strokeWidth={3} />
                      </span>
                    )}
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] ${
                          isActive
                            ? 'bg-[#5D7052]/12 text-[#5D7052]'
                            : isCompleted
                              ? 'bg-[#C18C5D]/12 text-[#C18C5D]'
                              : 'bg-[#F3EEE6] text-[#AFA18F]'
                        }`}
                      >
                        {isActive ? '当前' : isCompleted ? '完成' : '待开始'}
                      </span>
                    </div>
                    <p
                      className={`font-fraunces text-[1.15rem] leading-none transition-colors duration-300 ${
                        isActive
                          ? 'text-[#3F5A3C]'
                          : isCompleted
                            ? 'text-[#B57E4F]'
                            : 'text-[#8F8578]'
                      }`}
                    >
                      {step.label}
                    </p>
                    <p
                      className={`text-xs font-medium tracking-[0.08em] ${
                        isActive
                          ? 'text-[#5D7052]'
                          : isCompleted
                            ? 'text-[#A97C56]'
                            : 'text-[#B9AEA0]'
                      }`}
                    >
                      {step.helper}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {gates.length > 0 && (
          <div className="mt-6 rounded-[24px] border border-[#E7DFD5] bg-[#FCF9F4] p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                  Skill Checkpoints
                </p>
                <p className="text-sm text-[#78786C]">
                  当前模式下，哪些门禁需要人工确认，哪些会自动推进。
                </p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {gates.map((gate) => {
                const status = getGateStatus(gate, safeStep);
                const Icon = getCheckpointIcon(status);

                return (
                  <div
                    key={gate.key}
                    className={`rounded-[22px] border px-4 py-4 text-left ${
                      status === 'complete'
                        ? 'border-[#C18C5D] bg-[#FBF3EA]'
                        : status === 'current'
                          ? 'border-[#5D7052] bg-[#EEF3EB]'
                          : 'border-[#DED8CF] bg-white'
                    }`}
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <span className={`inline-flex h-9 w-9 items-center justify-center rounded-2xl ${
                        status === 'complete'
                          ? 'bg-[#C18C5D] text-white'
                          : status === 'current'
                            ? 'bg-[#5D7052] text-white'
                            : 'bg-[#F3EEE6] text-[#AFA18F]'
                      }`}>
                        <Icon size={16} />
                      </span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.16em] ${
                        status === 'complete'
                          ? 'bg-[#C18C5D]/12 text-[#C18C5D]'
                          : status === 'current'
                            ? 'bg-[#5D7052]/12 text-[#5D7052]'
                            : 'bg-[#F3EEE6] text-[#AFA18F]'
                      }`}>
                        {status === 'complete' ? '已通过' : status === 'current' ? '当前门禁' : '未到达'}
                      </span>
                    </div>
                    <p className="font-fraunces text-lg text-[#2C2C24]">{gate.label}</p>
                    <p className="mt-2 text-xs leading-5 text-[#78786C]">{gate.detail}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default StepIndicator;
