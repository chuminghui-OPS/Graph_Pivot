import fs from "fs/promises";
import path from "path";
import type { GetServerSideProps, InferGetServerSidePropsType } from "next";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/router";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";

type TutorialSpec = {
  id: string;
  title: string;
  fileName: string;
};

type TutorialDoc = TutorialSpec & {
  content: string;
  error: string | null;
};

const tutorialSpecs: TutorialSpec[] = [
  { id: "google-api", title: "Google API 获取教程", fileName: "Google _Api获取教程.md" },
  { id: "openrouter-api", title: "OpenRouter API 获取教程", fileName: "OpenRouter_Api获取教程.md" },
  { id: "tokenpony-token", title: "TokenPony Token 获取", fileName: "TokenPony的token的获取.md" },
  { id: "aliyun-bailian", title: "阿里百炼云", fileName: "阿里百炼云.md" },
  { id: "siliconflow-token", title: "硅基流动 Token 免费领取", fileName: "硅基流动token免费领取教学.md" },
  { id: "magic-community-token", title: "魔法社区 Token 获取流程", fileName: "魔法社区的token的获取流程.md" },
  { id: "tencent-hunyuan", title: "腾讯混元大模型平台", fileName: "腾讯混元大模型平台使用教程.md" },
  { id: "volcano-ark", title: "字节火山方舟", fileName: "字节火山方舟.md" }
];

export const getServerSideProps: GetServerSideProps<{ tutorials: TutorialDoc[] }> = async () => {
  const tutorialsDir = path.join(process.cwd(), "content", "free-api-tutorials");

  const tutorials = await Promise.all(
    tutorialSpecs.map(async (spec) => {
      try {
        const filePath = path.join(tutorialsDir, spec.fileName);
        const content = await fs.readFile(filePath, "utf8");
        return {
          ...spec,
          content,
          error: null
        };
      } catch (error: any) {
        return {
          ...spec,
          content: `# ${spec.title}\n\n教程文件暂时不可用。\n\n文件名：\`${spec.fileName}\`\n路径：\`${tutorialsDir}\``,
          error: error?.message || "读取失败"
        };
      }
    })
  );

  return {
    props: {
      tutorials
    }
  };
};

function FreeApiTutorialsPage({
  tutorials
}: InferGetServerSidePropsType<typeof getServerSideProps>) {
  const router = useRouter();
  const [activeId, setActiveId] = useState<string>(tutorials[0]?.id || "");

  const activeTutorial = useMemo(
    () => tutorials.find((item) => item.id === activeId) || tutorials[0] || null,
    [tutorials, activeId]
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo">GP</div>
          <div className="brand-meta">
            <div className="brand-name">Graph Pivot</div>
            <div className="brand-desc">知识图谱阅读器</div>
          </div>
        </div>
        <nav className="top-nav">
          <Link href="/" className="nav-link">
            知识图谱
          </Link>
          <Link href="/public" className="nav-link">
            公共书库
          </Link>
          <Link href="/account" className="nav-link">
            个人中心
          </Link>
          <Link
            href="/free-api-tutorials"
            className={`nav-link ${router.pathname === "/free-api-tutorials" ? "active" : ""}`}
          >
            免费 API 教程
          </Link>
        </nav>
      </header>

      <div className="tutorial-page">
        <aside className="tutorial-sidebar">
          <div className="tutorial-sidebar-title">获取免费 API 教程</div>
          <div className="tutorial-sidebar-subtitle">共 {tutorials.length} 份教程</div>
          <nav className="tutorial-nav-list">
            {tutorials.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`tutorial-nav-item ${item.id === activeTutorial?.id ? "active" : ""}`}
                onClick={() => setActiveId(item.id)}
              >
                {item.title}
              </button>
            ))}
          </nav>
        </aside>

        <main className="tutorial-main">
          {activeTutorial ? (
            <>
              <header className="tutorial-header">
                <h1 className="tutorial-title">{activeTutorial.title}</h1>
                <div className="tutorial-meta">{activeTutorial.fileName}</div>
              </header>
              <article className="tutorial-content markdown-body">
                {activeTutorial.error ? (
                  <div className="notice">
                    读取文件失败：{activeTutorial.error}
                  </div>
                ) : null}
                <ReactMarkdown rehypePlugins={[rehypeRaw]}>{activeTutorial.content}</ReactMarkdown>
              </article>
            </>
          ) : (
            <div className="empty">暂无教程内容</div>
          )}
        </main>
      </div>
    </div>
  );
}

export default FreeApiTutorialsPage;
