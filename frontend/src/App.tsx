
import { useState, useEffect } from 'react';
import { LogOut, FolderOpen } from 'lucide-react';
import NoiseOverlay from './components/NoiseOverlay';
import StepIndicator from './components/StepIndicator';
import AuthView from './views/AuthView';
import InputView from './views/InputView';
import ResearchView from './views/ResearchView';
import OutlineEditor from './views/OutlineEditor';
import BlueprintEditor from './views/BlueprintEditor';
import StyleSelector from './views/StyleSelector';
import RenderPathSelector, { type RenderPathPreference } from './views/RenderPathSelector';
import GenerationResultView from './views/GenerationResultView';
import HistoryView from './views/HistoryView';
import {
  api,
  tokenManager,
  type CollaborationMode,
  type OutlineItem,
  type SkillRuntime,
  type SkillRuntimeSummary,
  type SlideBlueprintItem,
  type UploadedDocument,
  type User,
} from './api/client';
import { seedlingIcon } from './assets/icons';

type AppView = 'wizard' | 'history';

function getStepHint(step: number, selectedStyleId: string): string {
  switch (step) {
    case 0:
      return '输入主题或上传论文，系统会据此启动创作';
    case 1:
      return '研究员正在检索资料并为内容策划做准备';
    case 2:
      return '请确认结构与章节顺序，避免后续返工';
    case 3:
      return '把章节拆成真正的页级蓝图，确认每一页要讲什么';
    case 4:
      return selectedStyleId ? '继续选择渲染策略，确定最终输出方式' : '先挑选最适合这份内容的视觉风格';
    case 5:
      return '系统正在生成幻灯片并准备可下载的 PPT 文件';
    default:
      return '流程会自动推进到下一阶段';
  }
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [view, setView] = useState<AppView>('wizard');
  const [step, setStep] = useState(0);
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [outline, setOutline] = useState<OutlineItem[]>([]);
  const [slideBlueprint, setSlideBlueprint] = useState<SlideBlueprintItem[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [selectedSkillId, setSelectedSkillId] = useState('huashu-slides');
  const [skillRuntime, setSkillRuntime] = useState<SkillRuntime | null>(null);
  const [availableSkills, setAvailableSkills] = useState<SkillRuntimeSummary[]>([]);
  const [collaborationMode, setCollaborationMode] = useState<CollaborationMode>('guided');
  const [uploadedDoc, setUploadedDoc] = useState<UploadedDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 检查登录状态
  useEffect(() => {
    const initializeApp = async () => {
      const token = tokenManager.get();
      try {
        const skillsPayload = await api.getSkills();
        const nextSkills = skillsPayload.skills ?? [];
        setAvailableSkills(nextSkills);
        const initialSkillId = nextSkills[0]?.skill_id ?? 'huashu-slides';
        setSelectedSkillId(initialSkillId);
        const runtime = await api.getSkillRuntime(initialSkillId);
        setSkillRuntime(runtime);
        setCollaborationMode(runtime.default_collaboration_mode ?? 'guided');
      }

      catch {
        setAvailableSkills([]);
        setSelectedSkillId('huashu-slides');
        setCollaborationMode('guided');
      }

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
    initializeApp();
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
    setView('wizard');
    setSessionId(null);
    setSelectedStyleId('');
    setPrompt('');
    setOutline([]);
    setSlideBlueprint([]);
    setError(null);
    setUploadedDoc(null);
  };

  const handleRestart = () => {
    setStep(0);
    setView('wizard');
    setSessionId(null);
    setSelectedStyleId('');
    setSlideBlueprint([]);
    setUploadedDoc(null);
  };

  const handleStartProject = async () => {
    try {
      setError(null);
      const res = await api.createProject(
        prompt,
        undefined,
        uploadedDoc?.source_docs,
        !!uploadedDoc,
        selectedSkillId,
        collaborationMode,
      );
      setSessionId(res.session_id);
      setStep(1);
    } catch (err: unknown) {
      setError(getErrorMessage(err, '项目创建失败'));
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
      await api.updateSessionStyle(sessionId, selectedStyleId, preference);
      setStep(5);
    } catch (err: unknown) {
      setError(getErrorMessage(err, '渲染路径设置失败'));
    }
  };

  const handleOutlineConfirm = async (updatedOutline: OutlineItem[]) => {
    if (!sessionId) return;
    try {
      await api.updateOutline(sessionId, updatedOutline);
      setOutline(updatedOutline);
      setSlideBlueprint([]);
      setStep(3);
    } catch (err: unknown) {
      setError(getErrorMessage(err, '大纲更新失败'));
    }
  };

  const handleBlueprintConfirm = async (updatedBlueprint: SlideBlueprintItem[]) => {
    setSlideBlueprint(updatedBlueprint);
    setStep(4);
  };

  const handleSkillChange = async (skillId: string) => {
    try {
      setError(null);
      setSelectedSkillId(skillId);
      const runtime = await api.getSkillRuntime(skillId);
      setSkillRuntime(runtime);
      setCollaborationMode(runtime.default_collaboration_mode ?? 'guided');
    } catch (err: unknown) {
      setError(getErrorMessage(err, '加载 SkillRuntime 失败'));
    }
  };

  const handleFullAutoContinue = async (finalOutline: OutlineItem[]) => {
    if (!sessionId) return;

    try {
      await api.updateOutline(sessionId, finalOutline);
      const generatedBlueprint = await api.generateBlueprint(sessionId);
      const blueprint = generatedBlueprint.slide_blueprint ?? [];
      await api.updateBlueprint(sessionId, blueprint);
      setSlideBlueprint(blueprint);

      const recommended = await api.getStyleRecommendations(prompt);
      const fallbackStyles = await api.getStyles();
      const autoStyleId = recommended[0] ?? fallbackStyles[0]?.id ?? '';
      if (!autoStyleId) {
        throw new Error('没有可用的风格可用于 Full Auto');
      }

      const defaultPath = skillRuntime?.default_render_path === 'path_b' ? 'path_b' : 'path_a';
      setSelectedStyleId(autoStyleId);
      await api.updateSessionStyle(sessionId, autoStyleId, defaultPath);
      setStep(5);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Full Auto 自动推进失败，已回退到手动确认流程'));
      setStep(2);
    }
  };

  const handleResearchComplete = async (finalOutline: OutlineItem[]) => {
    setOutline(finalOutline);

    if (collaborationMode === 'full_auto') {
      await handleFullAutoContinue(finalOutline);
      return;
    }

    setStep(2);
  };

  const handleNewProject = () => {
    setView('wizard');
    setStep(0);
    setPrompt('');
    setSessionId(null);
    setSelectedStyleId('');
    setUploadedDoc(null);
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
          <button
            onClick={handleRestart}
            className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          >
            <img src={seedlingIcon} alt="OrganicSlides" className="w-8 h-8 drop-shadow-sm" />
            <span className="font-fraunces font-bold text-lg text-[#2C2C24]">OrganicSlides</span>
          </button>
          <div className="flex items-center gap-4 text-sm font-bold text-[#78786C]">
            {user && (
              <>
                <button
                  onClick={() => setView(view === 'history' ? 'wizard' : 'history')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors ${
                    view === 'history'
                      ? 'bg-[#5D7052]/10 text-[#5D7052]'
                      : 'hover:text-[#5D7052] hover:bg-[#5D7052]/5'
                  }`}
                >
                  <FolderOpen size={16} />
                  我的项目
                </button>
                <span className="text-[#5D7052]">{user.username}</span>
                <button onClick={handleLogout} className="hover:text-[#A85448] flex items-center gap-1">
                  <LogOut size={16} /> 退出
                </button>
              </>
            )}
            {user && view === 'wizard' && step > 0 && (
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

        {/* Not logged in */}
        {!user && <AuthView onAuthSuccess={handleAuthSuccess} />}

        {/* Logged in - History view */}
        {user && view === 'history' && (
          <HistoryView onNewProject={handleNewProject} />
        )}

        {/* Logged in - Wizard view */}
        {user && view === 'wizard' && (
          <>
            <StepIndicator
              currentStep={step}
              currentStepHint={getStepHint(step, selectedStyleId)}
              skillRuntime={skillRuntime}
              collaborationMode={collaborationMode}
            />

            <div className="min-h-[500px] transition-all duration-500 ease-in-out">
              {step === 0 && (
                <InputView
                  prompt={prompt}
                  setPrompt={setPrompt}
                  onNext={handleStartProject}
                  uploadedDoc={uploadedDoc}
                  onUploadSuccess={setUploadedDoc}
                  onClearUpload={() => setUploadedDoc(null)}
                  availableSkills={availableSkills}
                  selectedSkillId={selectedSkillId}
                  skillRuntime={skillRuntime}
                  collaborationMode={collaborationMode}
                  onSkillChange={handleSkillChange}
                  onCollaborationModeChange={setCollaborationMode}
                />
              )}

              {step === 1 && sessionId && (
                <ResearchView
                  sessionId={sessionId}
                  onComplete={handleResearchComplete}
                />
              )}

              {step === 2 && sessionId && (
                <OutlineEditor
                  initialOutline={outline}
                  onNext={(updated) => handleOutlineConfirm(updated)}
                />
              )}

              {step === 3 && !selectedStyleId && (
                <BlueprintEditor
                  sessionId={sessionId!}
                  initialBlueprint={slideBlueprint}
                  onNext={handleBlueprintConfirm}
                />
              )}

              {step === 4 && !selectedStyleId && (
                <StyleSelector
                  userIntent={prompt}
                  onNext={handleStyleSelected}
                />
              )}

              {step === 4 && selectedStyleId && (
                <RenderPathSelector
                  onNext={handleRenderPathSelected}
                  onBack={() => setSelectedStyleId('')}
                />
              )}

              {step === 5 && sessionId && (
                <GenerationResultView
                  sessionId={sessionId}
                  collaborationMode={collaborationMode}
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
