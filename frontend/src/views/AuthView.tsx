
import React, { useState } from 'react';
import { Mail, Lock, User, ArrowRight, Loader2 } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { api } from '../api/client';
import { nutLeavesIcon } from '../assets/icons';

interface AuthViewProps {
    onAuthSuccess: () => void;
}

const getErrorMessage = (error: unknown, fallback: string) =>
    error instanceof Error && error.message ? error.message : fallback;

const AuthView: React.FC<AuthViewProps> = ({ onAuthSuccess }) => {
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            if (isLogin) {
                await api.login(email, password);
            } else {
                await api.register(email, username, password);
            }
            onAuthSuccess();
        } catch (err: unknown) {
            setError(getErrorMessage(err, '认证失败'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col items-center text-center animate-in fade-in slide-in-from-bottom-4 duration-700 max-w-md mx-auto">
            <img src={nutLeavesIcon} alt="" className="w-20 h-20 mb-4 opacity-80 drop-shadow-md" />
            <h1 className="font-fraunces text-4xl md:text-5xl text-[#2C2C24] mb-4 leading-tight">
                {isLogin ? '欢迎回来' : '加入我们'}
            </h1>
            <p className="text-[#78786C] text-lg mb-8">
                {isLogin ? '登录以继续您的创作之旅' : '创建账户，开启 AI 演示文稿之旅'}
            </p>

            <form onSubmit={handleSubmit} className="w-full space-y-4">
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl text-sm">
                        {error}
                    </div>
                )}

                <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-[#78786C]" size={20} />
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="邮箱地址"
                        required
                        className="w-full bg-white/60 border border-[#DED8CF] rounded-2xl py-4 pl-12 pr-4 text-[#2C2C24] placeholder-[#78786C]/50 focus:outline-none focus:ring-2 focus:ring-[#5D7052]/30"
                    />
                </div>

                {!isLogin && (
                    <div className="relative">
                        <User className="absolute left-4 top-1/2 -translate-y-1/2 text-[#78786C]" size={20} />
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="用户名"
                            required={!isLogin}
                            className="w-full bg-white/60 border border-[#DED8CF] rounded-2xl py-4 pl-12 pr-4 text-[#2C2C24] placeholder-[#78786C]/50 focus:outline-none focus:ring-2 focus:ring-[#5D7052]/30"
                        />
                    </div>
                )}

                <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-[#78786C]" size={20} />
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="密码"
                        required
                        minLength={6}
                        className="w-full bg-white/60 border border-[#DED8CF] rounded-2xl py-4 pl-12 pr-4 text-[#2C2C24] placeholder-[#78786C]/50 focus:outline-none focus:ring-2 focus:ring-[#5D7052]/30"
                    />
                </div>

                <BlobButton
                    type="submit"
                    disabled={loading}
                    icon={loading ? Loader2 : ArrowRight}
                    className="w-full mt-6"
                >
                    {loading ? '处理中...' : (isLogin ? '登录' : '注册')}
                </BlobButton>
            </form>

            <p className="mt-8 text-[#78786C]">
                {isLogin ? '还没有账户？' : '已有账户？'}
                <button
                    onClick={() => { setIsLogin(!isLogin); setError(null); }}
                    className="text-[#5D7052] font-bold ml-1 hover:underline"
                >
                    {isLogin ? '立即注册' : '去登录'}
                </button>
            </p>
        </div>
    );
};

export default AuthView;
