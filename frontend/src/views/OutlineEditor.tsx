
import React, { useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import type { OutlineItem } from '../api/client';

interface OutlineEditorProps {
    initialOutline: OutlineItem[];
    onNext: (updatedOutline: OutlineItem[]) => void;
}

const createOutlineItem = (): OutlineItem => ({
    id: globalThis.crypto?.randomUUID?.() ?? `outline-${Date.now()}`,
    title: '新章节',
    type: 'Content',
});

const cloneOutline = (items: OutlineItem[]): OutlineItem[] =>
    items.map((item) => ({ ...item }));

const OutlineEditor: React.FC<OutlineEditorProps> = ({ initialOutline, onNext }) => {
    const [outline, setOutline] = useState<OutlineItem[]>(() => cloneOutline(initialOutline));
    const [isSubmitting, setIsSubmitting] = useState(false);

    const updateOutlineTitle = (id: string, title: string) => {
        setOutline((currentOutline) =>
            currentOutline.map((item) =>
                item.id === id ? { ...item, title } : item,
            ),
        );
    };

    const removeOutlineItem = (id: string) => {
        setOutline((currentOutline) => currentOutline.filter((item) => item.id !== id));
    };

    const addOutlineItem = () => {
        setOutline((currentOutline) => [...currentOutline, createOutlineItem()]);
    };

    const handleNext = async () => {
        setIsSubmitting(true);
        await onNext(cloneOutline(outline));
        setIsSubmitting(false);
    };

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
                <h2 className="font-fraunces text-3xl text-[#2C2C24]">策划师建议的大纲</h2>
                <p className="text-[#78786C]">请审阅并调整演示文稿的结构，确认无误后我们将开始生成。</p>
            </div>

            <div className="bg-[#FEFEFA] border border-[#DED8CF] rounded-[32px] p-8 shadow-sm mb-8 relative overflow-hidden">
                {/* Paper texture overlay */}
                <div className="absolute inset-0 opacity-[0.4] mix-blend-multiply pointer-events-none" style={{ backgroundImage: "url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPgo8cmVjdCB3aWR0aD0iNCIgaGVpZ2h0PSI0IiBmaWxsPSIjZmZmIi8+CjxyZWN0IHdpZHRoPSIxIiBoZWlnaHQ9IjEiIGZpbGw9IiNjY2MiLz4KPC9zdmc+') " }}></div>

                <div className="space-y-4 relative z-10">
                    {outline.map((item, idx) => (
                        <div key={item.id} className="group flex items-center gap-4 bg-white/80 p-4 rounded-2xl border border-transparent hover:border-[#5D7052]/30 hover:shadow-md transition-all">
                            <div className="text-[#DED8CF] font-fraunces text-xl w-8 text-center">{idx + 1}</div>
                            <div className="flex-1">
                                <input
                                    value={item.title}
                                    onChange={(e) => updateOutlineTitle(item.id, e.target.value)}
                                    className="w-full bg-transparent font-bold text-[#2C2C24] focus:outline-none border-b border-transparent focus:border-[#5D7052]"
                                />
                                <div className="flex items-center gap-2 mt-1">
                                    <span className="text-xs bg-[#F0EBE5] text-[#78786C] px-2 py-0.5 rounded-full">{item.type}</span>
                                </div>
                            </div>
                            <div className="opacity-0 group-hover:opacity-100 flex gap-2">
                                <button
                                    onClick={() => removeOutlineItem(item.id)}
                                    className="p-2 hover:bg-[#A85448]/10 text-[#A85448] rounded-full transition-colors"
                                >
                                    <span className="text-lg">×</span>
                                </button>
                            </div>
                        </div>
                    ))}

                    <button
                        className="w-full py-4 border-2 border-dashed border-[#DED8CF] rounded-2xl text-[#78786C] hover:border-[#5D7052] hover:text-[#5D7052] transition-colors font-bold"
                        onClick={addOutlineItem}
                    >
                        + 添加章节
                    </button>
                </div>
            </div>

            <div className="flex justify-center gap-4">
                <BlobButton onClick={handleNext} icon={isSubmitting ? Loader2 : Check} disabled={isSubmitting}>
                    {isSubmitting ? "正在确认..." : "确认大纲并继续"}
                </BlobButton>
            </div>
        </div>
    );
};

export default OutlineEditor;
