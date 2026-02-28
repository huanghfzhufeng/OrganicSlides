
import { useState, useEffect } from 'react';
import { LogOut } from 'lucide-react';
import NoiseOverlay from './components/NoiseOverlay';
import StepIndicator from './components/StepIndicator';
import AuthView from './views/AuthView';
import InputView from './views/InputView';
import ResearchView from './views/ResearchView';
import OutlineEditor from './views/OutlineEditor';
import StyleSelector from './views/StyleSelector';
import RenderPathSelector, { type RenderPathPreference } from './views/RenderPathSelector';
import GenerationResultView from './views/GenerationResultView';
import { api, tokenManager, type OutlineItem, type User } from './api/client';
import { seedlingIcon } from './assets/icons';

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [step, setStep] = useState(0);
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [outline, setOutline] = useState<OutlineItem[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [renderPathPreference, setRenderPathPreference] = useState<RenderPathPreference>('auto');
  const [error, setError] = useState<string | null>(null);

  // 检查登录状态
  useEffect(() => {
    const checkAuth = async () => {
      const token = tokenManager.get();
      if (token) {
        try {
          const userData = await api.getMe();
          setUser(userData);
        } catch {
          tokenManager.remove();
        }
      }
      setIsLoading(false);
    };
    checkAuth();
  }, []);

  const handleAuthSuccess = async () => {
    try {
      const userData = await api.getMe();
      setUser(userData);
    } catch {
      setError('认证失败');
    }
  };

  const handleLogout = () => {
    api.logout();
    setUser(null);
    setStep(0);
    setSessionId(null);
    setSelectedStyleId('');
  };

  const handleRestart = () => {
    setStep(0);
    setSessionId(null);
    setSelectedStyleId('');
    setRenderPathPreference('auto');
  };

  const handleStartProject = async () => {
    try {
      setError(null);
      const res = await api.createProject(prompt);
      setSessionId(res.session_id);
      setStep(1);
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Style chosen → advance within step 3 to render path sub-step
  const handleStyleSelected = (styleId: string) => {
    setSelectedStyleId(styleId);
    // Stay on step 3; the render path selector will appear next
  };

  // Render path chosen → pass both style_id and render_path_preference to backend, start generation
  const handleRenderPathSelected = async (preference: RenderPathPreference) => {
    if (!sessionId) return;
    try {
      setError(null);
      setRenderPathPreference(preference);
      await api.updateSessionStyle(sessionId, selectedStyleId, preference);
      setStep(4);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleOutlineConfirm = async (updatedOutline: OutlineItem[]) => {
    if (!sessionId) return;
    try {
      await api.updateOutline(sessionId, updatedOutline);
      setOutline(updatedOutline);
      setStep(3);
    } catch (err: any) {
      setError(err.message);
    }
  };


  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#FDFCF8] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-[#5D7052] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FDFCF8] text-[#2C2C24] font-nunito overflow-x-hidden selection:bg-[#5D7052]/20 pb-20">

      <NoiseOverlay />

      {/* Header */}
      <nav className="sticky top-0 z-40 bg-[#FDFCF8]/80 backdrop-blur-md border-b border-[#DED8CF]/30 mb-8">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <img src={seedlingIcon} alt="OrganicSlides" className="w-8 h-8 drop-shadow-sm" />
            <span className="font-fraunces font-bold text-lg text-[#2C2C24]">OrganicSlides</span>
          </div>
          <div className="flex items-center gap-4 text-sm font-bold text-[#78786C]">
            {user && (
              <>
                <span className="text-[#5D7052]">{user.username}</span>
                <button onClick={handleLogout} className="hover:text-[#A85448] flex items-center gap-1">
                  <LogOut size={16} /> 退出
                </button>
              </>
            )}
            {user && step > 0 && (
              <button onClick={handleRestart} className="hover:text-[#5D7052]">
                重新开始
              </button>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6">

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl mb-6 text-center">
            {error}
          </div>
        )}

        {/* 未登录显示认证页面 */}
        {!user && <AuthView onAuthSuccess={handleAuthSuccess} />}

        {/* 已登录显示 Wizard */}
        {user && (
          <>
            <StepIndicator currentStep={step} />

            <div className="min-h-[500px] transition-all duration-500 ease-in-out">
              {step === 0 && (
                <InputView
                  prompt={prompt}
                  setPrompt={setPrompt}
                  onNext={handleStartProject}
                />
              )}

              {step === 1 && sessionId && (
                <ResearchView
                  sessionId={sessionId}
                  onComplete={(finalOutline) => {
                    setOutline(finalOutline);
                    setStep(2);
                  }}
                />
              )}

              {step === 2 && sessionId && (
                <OutlineEditor
                  initialOutline={outline}
                  onNext={(updated) => handleOutlineConfirm(updated)}
                />
              )}

              {step === 3 && !selectedStyleId && (
                <StyleSelector
                  userIntent={prompt}
                  onNext={handleStyleSelected}
                />
              )}

              {step === 3 && selectedStyleId && (
                <RenderPathSelector
                  onNext={handleRenderPathSelected}
                  onBack={() => setSelectedStyleId('')}
                />
              )}

              {step === 4 && sessionId && (
                <GenerationResultView
                  sessionId={sessionId}
                />
              )}
            </div>
          </>
        )}

      </main>
    </div>
  );
}

export default App;
