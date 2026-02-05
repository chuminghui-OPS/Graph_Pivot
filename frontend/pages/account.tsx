import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import {
  ApiAsset,
  UserBook,
  UserProfile,
  createAsset,
  deleteAsset,
  fetchAssets,
  fetchUserBooks,
  fetchUserProfile,
  updateAsset
} from "../lib/api";
import { supabase } from "../lib/supabase";

const PROVIDER_OPTIONS = [
  "OpenAI",
  "OpenRouter",
  "Azure OpenAI",
  "Claude",
  "Gemini",
  "Qwen",
  "Moonshot",
  "Groq"
];

export default function AccountPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [books, setBooks] = useState<UserBook[]>([]);
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [activeAssetId, setActiveAssetId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    name: "",
    provider: "OpenAI",
    api_mode: "openai_compatible",
    api_key: "",
    base_url: "",
    api_path: "",
    models: ""
  });
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/login");
      }
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.replace("/login");
      }
    });
    return () => data.subscription.unsubscribe();
  }, [router]);

  const activeAsset = useMemo(
    () => assets.find((item) => item.id === activeAssetId) || null,
    [assets, activeAssetId]
  );

  useEffect(() => {
    const load = async () => {
      try {
        const [profileData, booksData, assetsData] = await Promise.all([
          fetchUserProfile(),
          fetchUserBooks(),
          fetchAssets()
        ]);
        setProfile(profileData);
        setBooks(booksData);
        setAssets(assetsData);
        if (!activeAssetId && assetsData.length > 0) {
          setActiveAssetId(assetsData[0].id);
        }
      } catch (err: any) {
        setMessage(err.message || "加载失败");
      }
    };
    load();
  }, []);

  useEffect(() => {
    if (!activeAsset) return;
    setForm({
      name: activeAsset.name,
      provider: activeAsset.provider,
      api_mode: activeAsset.api_mode,
      api_key: activeAsset.api_key,
      base_url: activeAsset.base_url || "",
      api_path: activeAsset.api_path || "",
      models: (activeAsset.models || []).join(", ")
    });
  }, [activeAsset]);

  const handleSave = async () => {
    if (!activeAsset) return;
    const payload = {
      name: form.name,
      provider: form.provider,
      api_mode: form.api_mode,
      api_key: form.api_key,
      base_url: form.base_url || null,
      api_path: form.api_path || null,
      models: form.models
        ? form.models.split(",").map((m) => m.trim()).filter(Boolean)
        : []
    };
    try {
      const updated = await updateAsset(activeAsset.id, payload);
      setAssets((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("已保存");
    } catch (err: any) {
      setMessage(err.message || "保存失败");
    }
  };

  const handleCreate = async () => {
    try {
      const payload = {
        name: form.name,
        provider: form.provider,
        api_mode: form.api_mode,
        api_key: form.api_key,
        base_url: form.base_url || null,
        api_path: form.api_path || null,
        models: form.models
          ? form.models.split(",").map((m) => m.trim()).filter(Boolean)
          : []
      };
      const created = await createAsset(payload as any);
      setAssets((prev) => [created, ...prev]);
      setActiveAssetId(created.id);
      setShowModal(false);
    } catch (err: any) {
      setMessage(err.message || "创建失败");
    }
  };

  const handleDelete = async () => {
    if (!activeAsset) return;
    if (!confirm("确认删除该厂商配置？")) return;
    try {
      await deleteAsset(activeAsset.id);
      setAssets((prev) => prev.filter((item) => item.id !== activeAsset.id));
      setActiveAssetId(null);
      setMessage("已删除");
    } catch (err: any) {
      setMessage(err.message || "删除失败");
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push("/login");
  };

  return (
    <div className="account-page">
      <aside className="account-nav">
        <div className="nav-brand">Graph Pivot</div>
        <nav>
          <button className="nav-item active">个人中心</button>
          <button className="nav-item" onClick={() => router.push("/")}>
            知识图谱
          </button>
        </nav>
        <div className="nav-spacer" />
        <button className="nav-item" onClick={handleSignOut}>
          退出登录
        </button>
      </aside>

      <main className="account-main">
        <header className="account-header">
          <div>
            <div className="account-title">个人用户中心</div>
            <div className="account-subtitle">管理账户信息、API 资产与书籍</div>
          </div>
          <button
            className="primary"
            onClick={() => {
              setForm({
                name: "",
                provider: "OpenAI",
                api_mode: "openai_compatible",
                api_key: "",
                base_url: "",
                api_path: "",
                models: ""
              });
              setShowModal(true);
            }}
          >
            添加厂商
          </button>
        </header>

        {message ? <div className="notice">{message}</div> : null}

        <section className="profile-card">
          <div className="profile-main">
            <div className="avatar">
              {profile?.full_name?.[0] || profile?.email?.[0] || "U"}
            </div>
            <div>
              <div className="profile-name">{profile?.full_name || "未设置昵称"}</div>
              <div className="profile-email">{profile?.email || "-"}</div>
            </div>
          </div>
          <div className="profile-meta">
            <div>
              <div className="meta-label">套餐</div>
              <div className="meta-value">{profile?.plan || "Free"}</div>
            </div>
            <div>
              <div className="meta-label">处理书籍数</div>
              <div className="meta-value">{profile?.total_books || 0}</div>
            </div>
          </div>
        </section>

        <section className="asset-panel">
          <div className="asset-list">
            {assets.length === 0 ? (
              <div className="empty">暂无厂商配置</div>
            ) : (
              assets.map((asset) => (
                <button
                  key={asset.id}
                  className={asset.id === activeAssetId ? "asset-item active" : "asset-item"}
                  onClick={() => setActiveAssetId(asset.id)}
                >
                  <div className="asset-name">{asset.name}</div>
                  <div className="asset-provider">{asset.provider}</div>
                </button>
              ))
            )}
          </div>
          <div className="asset-detail">
            {activeAsset ? (
              <>
                <div className="detail-row">
                  <label>名称</label>
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </div>
                <div className="detail-row">
                  <label>API 模式</label>
                  <select
                    value={form.api_mode}
                    onChange={(e) => setForm({ ...form, api_mode: e.target.value })}
                  >
                    <option value="openai_compatible">OpenAI API 兼容</option>
                    <option value="native">原生</option>
                  </select>
                </div>
                <div className="detail-row">
                  <label>API 密钥</label>
                  <input
                    value={form.api_key}
                    onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  />
                </div>
                <div className="detail-grid">
                  <div className="detail-row">
                    <label>API 主机</label>
                    <input
                      value={form.base_url}
                      onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                    />
                  </div>
                  <div className="detail-row">
                    <label>API 路径</label>
                    <input
                      value={form.api_path}
                      onChange={(e) => setForm({ ...form, api_path: e.target.value })}
                    />
                  </div>
                </div>
                <div className="detail-row">
                  <label>模型列表（逗号分隔）</label>
                  <textarea
                    rows={3}
                    value={form.models}
                    onChange={(e) => setForm({ ...form, models: e.target.value })}
                  />
                </div>
                <div className="detail-actions">
                  <button className="ghost" onClick={handleDelete}>
                    删除
                  </button>
                  <button className="primary" onClick={handleSave}>
                    保存
                  </button>
                </div>
              </>
            ) : (
              <div className="empty">选择左侧厂商查看详情</div>
            )}
          </div>
        </section>

        <section className="books-panel">
          <div className="panel-title">我的书籍 / 知识库</div>
          <div className="book-grid">
            {books.length === 0 ? (
              <div className="empty">暂无书籍</div>
            ) : (
              books.map((book) => (
                <div key={book.book_id} className="book-card">
                  <div className="book-cover">{book.title?.slice(0, 2) || "书"}</div>
                  <div className="book-info">
                    <div className="book-title">{book.title}</div>
                    <div className="book-id">{book.book_id}</div>
                    <div className="book-date">{book.created_at || "-"}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {showModal ? (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">添加厂商</div>
            <div className="detail-row">
              <label>名称</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="detail-row">
              <label>厂商</label>
              <select
                value={form.provider}
                onChange={(e) => setForm({ ...form, provider: e.target.value })}
              >
                {PROVIDER_OPTIONS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
            <div className="detail-row">
              <label>API 密钥</label>
              <input
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              />
            </div>
            <div className="detail-row">
              <label>API 主机</label>
              <input
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              />
            </div>
            <div className="detail-row">
              <label>API 路径</label>
              <input
                value={form.api_path}
                onChange={(e) => setForm({ ...form, api_path: e.target.value })}
              />
            </div>
            <div className="detail-row">
              <label>模型（逗号分隔）</label>
              <textarea
                rows={3}
                value={form.models}
                onChange={(e) => setForm({ ...form, models: e.target.value })}
              />
            </div>
            <div className="detail-actions">
              <button className="ghost" onClick={() => setShowModal(false)}>
                取消
              </button>
              <button className="primary" onClick={handleCreate}>
                创建
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
