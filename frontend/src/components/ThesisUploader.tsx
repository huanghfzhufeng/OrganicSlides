import React, { useCallback, useRef, useState } from 'react';
import { Paperclip, FileText, X, AlertCircle, Loader2 } from 'lucide-react';
import { api, type UploadedDocument } from '../api/client';

interface ThesisUploaderProps {
    uploadedDoc: UploadedDocument | null;
    onUploadSuccess: (doc: UploadedDocument) => void;
    onClear: () => void;
}

const ACCEPTED_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];
const ACCEPTED_EXTENSIONS = '.pdf,.docx';
const MAX_SIZE_MB = 15;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

/**
 * Inline thesis uploader — renders as a compact element
 * designed to live inside the input card's bottom bar.
 *
 * States:
 *   idle      → small "上传论文" button
 *   uploading → inline spinner
 *   done      → file chip with remove button
 */
const ThesisUploader: React.FC<ThesisUploaderProps> = ({
    uploadedDoc,
    onUploadSuccess,
    onClear,
}) => {
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const validateFile = useCallback((file: File): string | null => {
        if (!ACCEPTED_TYPES.includes(file.type)) {
            const ext = file.name.split('.').pop()?.toLowerCase();
            if (ext !== 'pdf' && ext !== 'docx') {
                return '仅支持 PDF 和 DOCX 格式';
            }
        }
        if (file.size > MAX_SIZE_BYTES) {
            return `文件过大（${(file.size / 1024 / 1024).toFixed(1)}MB），最大 ${MAX_SIZE_MB}MB`;
        }
        if (file.size === 0) {
            return '文件内容为空';
        }
        return null;
    }, []);

    const handleUpload = useCallback(async (file: File) => {
        const validationError = validateFile(file);
        if (validationError) {
            setError(validationError);
            return;
        }

        setError(null);
        setUploading(true);

        try {
            const result = await api.uploadDocument(file);
            setUploading(false);
            onUploadSuccess(result);
        } catch (err: any) {
            setUploading(false);
            setError(err.message || '上传失败，请重试');
        }
    }, [validateFile, onUploadSuccess]);

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) handleUpload(file);
        if (inputRef.current) inputRef.current.value = '';
    }, [handleUpload]);

    const handleClear = useCallback(() => {
        setError(null);
        onClear();
    }, [onClear]);

    return (
        <div className="flex flex-col gap-1">
            {/* Uploaded file chip */}
            {uploadedDoc && (
                <div className="flex items-center gap-2 bg-[#5D7052]/8 border border-[#5D7052]/15 rounded-xl px-3 py-2 mx-4 mb-1">
                    <FileText size={14} className="text-[#5D7052] shrink-0" />
                    <div className="flex-1 min-w-0">
                        <span className="text-xs font-bold text-[#2C2C24] truncate block">
                            {uploadedDoc.filename}
                        </span>
                        <span className="text-[10px] text-[#78786C]">
                            {uploadedDoc.chapters.length} 个章节 · {uploadedDoc.chunk_count} 个文本块
                        </span>
                    </div>
                    <button
                        onClick={handleClear}
                        className="w-5 h-5 rounded-full hover:bg-[#A85448]/10 flex items-center justify-center shrink-0 transition-colors"
                        title="移除文件"
                    >
                        <X size={12} className="text-[#78786C] hover:text-[#A85448]" />
                    </button>
                </div>
            )}

            {/* Bottom bar row: upload button / uploading spinner */}
            <div className="flex items-center">
                <input
                    ref={inputRef}
                    type="file"
                    accept={ACCEPTED_EXTENSIONS}
                    onChange={handleFileSelect}
                    className="hidden"
                />

                {uploading ? (
                    <span className="flex items-center gap-1.5 text-sm text-[#78786C] px-3 py-1.5">
                        <Loader2 size={14} className="text-[#5D7052] animate-spin" />
                        解析中...
                    </span>
                ) : !uploadedDoc ? (
                    <button
                        onClick={() => inputRef.current?.click()}
                        className="flex items-center gap-1.5 text-sm text-[#78786C] hover:text-[#5D7052] px-3 py-1.5 rounded-full hover:bg-[#5D7052]/5 transition-colors"
                        title={`上传论文（PDF/DOCX，最大 ${MAX_SIZE_MB}MB）`}
                    >
                        <Paperclip size={14} />
                        上传论文
                    </button>
                ) : null}
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-center gap-1.5 px-4 text-xs text-[#A85448]">
                    <AlertCircle size={12} />
                    <span>{error}</span>
                </div>
            )}
        </div>
    );
};

export default ThesisUploader;
