import React from 'react';
import { Bot, CheckCircle2, Compass, Users, Zap } from 'lucide-react';
import type { CollaborationMode, SkillRuntime, SkillRuntimeSummary } from '../api/client';

interface SkillRuntimePanelProps {
    availableSkills: SkillRuntimeSummary[];
    skillRuntime: SkillRuntime | null;
    selectedSkillId: string;
    collaborationMode: CollaborationMode;
    onSkillChange: (skillId: string) => void;
    onCollaborationModeChange: (mode: CollaborationMode) => void;
}

const MODE_ICON: Record<CollaborationMode, React.ComponentType<{ size?: number; className?: string }>> = {
    full_auto: Zap,
    guided: Compass,
    collaborative: Users,
};

const MODE_LABEL: Record<CollaborationMode, string> = {
    full_auto: 'Full Auto',
    guided: 'Guided',
    collaborative: 'Collaborative',
};

const SkillRuntimePanel: React.FC<SkillRuntimePanelProps> = ({
    availableSkills,
    skillRuntime,
    selectedSkillId,
    collaborationMode,
    onSkillChange,
    onCollaborationModeChange,
}) => {
    const runtimeModes = skillRuntime?.supported_collaboration_modes ?? [];
    const selectedMode = runtimeModes.find((item) => item.key === collaborationMode);

    return (
        <section className="mb-8 w-full rounded-[28px] border border-[#DED8CF] bg-white/78 p-5 text-left shadow-[0_28px_60px_-50px_rgba(93,112,82,0.75)] backdrop-blur-sm">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-[#A38B74]">
                        Skill Runtime
                    </p>
                    <h3 className="mt-1 font-fraunces text-2xl text-[#2C2C24]">
                        当前技能：{skillRuntime?.name ?? selectedSkillId}
                    </h3>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-[#78786C]">
                        {skillRuntime?.description ?? '将本地 skill 的流程、checkpoint、路径偏好注入到运行时。'}
                    </p>
                </div>
                <div className="inline-flex items-center gap-2 self-start rounded-full border border-[#DED8CF] bg-[#F9F5EE] px-3 py-2 text-xs font-bold text-[#5D7052]">
                    <Bot size={15} />
                    <span>{MODE_LABEL[collaborationMode]}</span>
                </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                <div className="rounded-[24px] border border-[#E7DFD5] bg-[#FCF9F4] p-4">
                    <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                        激活 Skill
                    </label>
                    <select
                        value={selectedSkillId}
                        onChange={(e) => onSkillChange(e.target.value)}
                        className="mb-3 w-full rounded-2xl border border-[#DED8CF] bg-white px-4 py-3 text-sm font-bold text-[#2C2C24] focus:border-[#5D7052] focus:outline-none"
                    >
                        {availableSkills.map((skill) => (
                            <option key={skill.skill_id} value={skill.skill_id}>
                                {skill.name}
                            </option>
                        ))}
                    </select>

                    <div className="space-y-2 text-xs leading-6 text-[#78786C]">
                        <div className="flex items-center justify-between rounded-2xl bg-white px-3 py-2">
                            <span>默认路径</span>
                            <span className="font-bold text-[#5D7052]">
                                {skillRuntime?.default_render_path === 'path_b' ? 'Path B' : 'Path A'}
                            </span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl bg-white px-3 py-2">
                            <span>参考文件</span>
                            <span className="font-bold text-[#5D7052]">
                                {skillRuntime?.reference_files.length ?? 0} 份
                            </span>
                        </div>
                        <div className="rounded-2xl bg-white px-3 py-3">
                            <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.16em] text-[#A38B74]">
                                设计哲学
                            </p>
                            <p>{skillRuntime?.design_philosophy ?? 'Context, not control'}</p>
                        </div>
                    </div>
                </div>

                <div className="rounded-[24px] border border-[#E7DFD5] bg-[#FCF9F4] p-4">
                    <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                        协作模式
                    </p>
                    <div className="grid gap-3 md:grid-cols-3">
                        {runtimeModes.map((mode) => {
                            const isActive = mode.key === collaborationMode;
                            const Icon = MODE_ICON[mode.key];

                            return (
                                <button
                                    key={mode.key}
                                    type="button"
                                    onClick={() => onCollaborationModeChange(mode.key)}
                                    className={`rounded-[22px] border px-4 py-4 text-left transition-all ${
                                        isActive
                                            ? 'border-[#5D7052] bg-[#EEF3EB] shadow-[0_16px_30px_-24px_rgba(93,112,82,0.95)]'
                                            : 'border-[#DED8CF] bg-white hover:border-[#C9B9A6]'
                                    }`}
                                >
                                    <div className="mb-3 flex items-center justify-between">
                                        <span className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl ${
                                            isActive ? 'bg-[#5D7052] text-white' : 'bg-[#F3EEE6] text-[#A38B74]'
                                        }`}>
                                            <Icon size={18} />
                                        </span>
                                        {isActive && <CheckCircle2 size={18} className="text-[#5D7052]" />}
                                    </div>
                                    <p className="font-fraunces text-lg text-[#2C2C24]">{MODE_LABEL[mode.key]}</p>
                                    <p className="mt-2 text-xs leading-5 text-[#78786C]">{mode.fit}</p>
                                    <p className="mt-3 text-[11px] leading-5 text-[#A38B74]">
                                        Checkpoint：{mode.checkpoints}
                                    </p>
                                </button>
                            );
                        })}
                    </div>

                    <div className="mt-4 rounded-[20px] border border-dashed border-[#D8CEC0] bg-white/80 px-4 py-3 text-xs leading-6 text-[#78786C]">
                        当前模式说明：
                        <span className="ml-1 font-bold text-[#5D7052]">
                            {selectedMode?.label ?? MODE_LABEL[collaborationMode]}
                        </span>
                        <span className="ml-2">{selectedMode?.checkpoints ?? '按系统默认门禁推进'}</span>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default SkillRuntimePanel;
