import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import dynamic from "next/dynamic";
import {
  ApiAsset,
  UserBook,
  UserProfile,
  UserUsageBookRow,
  createAsset,
  deleteAsset,
  discoverAssetModels,
  fetchAssets,
  fetchUserBooks,
  fetchUserUsage,
  fetchUserProfile,
  updateAsset
} from "../lib/api";
import { getSupabaseClient, hasSupabaseConfig } from "../lib/supabase";

function AccountPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [books, setBooks] = useState<UserBook[]>([]);
  const [usageByBook, setUsageByBook] = useState<Record<string, UserUsageBookRow>>({});
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [activeAssetId, setActiveAssetId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    provider: "OpenAI",
    api_mode: "openai_compatible"
  });
  const [newModelName, setNewModelName] = useState("");
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelSearch, setModelSearch] = useState("");
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
  const hasConfig = hasSupabaseConfig();

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      setMessage("缺少 Supabase 配置，请检查环境变量。");
      return;
    }
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

  const filteredAvailableModels = useMemo(() => {
    const q = modelSearch.trim().toLowerCase();
    if (!q) return availableModels;
    return availableModels.filter((m) => m.toLowerCase().includes(q));
  }, [availableModels, modelSearch]);

  useEffect(() => {
    const load = async () => {
      try {
        const [profileData, booksData, assetsData, usageData] = await Promise.all([
          fetchUserProfile(),
          fetchUserBooks(),
          fetchAssets(),
          fetchUserUsage()
        ]);
        setProfile(profileData);
        setBooks(booksData);
        setAssets(assetsData);
        const usageMap: Record<string, UserUsageBookRow> = {};
        for (const row of usageData) {
          usageMap[row.book_id] = row;
        }
        setUsageByBook(usageMap);
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
      api_key: "",
      base_url: activeAsset.base_url || "",
      api_path: activeAsset.api_path || "",
      models: (activeAsset.models || []).join(", ")
    });
  }, [activeAsset]);

  const handleSave = async () => {
    if (!activeAsset) return;
    const payload: any = {
      name: form.name,
      provider: form.provider,
      api_mode: form.api_mode,
      base_url: form.base_url || null,
      api_path: form.api_path || null,
      models: form.models
        ? form.models.split(",").map((m) => m.trim()).filter(Boolean)
        : []
    };
    if (form.api_key) {
      payload.api_key = form.api_key;
    }
    try {
      const updated = await updateAsset(activeAsset.id, payload);
      setAssets((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("已保存");
    } catch (err: any) {
      setMessage(err.message || "保存失败");
    }
  };

  const _parseModels = (value: string) =>
    value
      ? value
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      : [];

  const handleAddModel = async () => {
    if (!activeAsset) return;
    const model = newModelName.trim();
    if (!model) {
      setMessage("请输入模型名称");
      return;
    }
    const models = _parseModels(form.models);
    if (models.includes(model)) {
      setMessage("该模型已存在");
      return;
    }
    const next = [...models, model];
    setForm({ ...form, models: next.join(", ") });
    setNewModelName("");
    try {
      const updated = await updateAsset(activeAsset.id, { models: next });
      setAssets((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("已添加模型");
      setShowModelPicker(false);
    } catch (err: any) {
      setMessage(err.message || "添加模型失败");
    }
  };

  const handleFetchModels = async () => {
    if (!activeAsset) return;
    try {
      // Save base_url/api_key first so backend can use it to fetch models.
      const payload: any = {
        base_url: form.base_url || null,
        api_path: form.api_path || null
      };
      if (form.api_key) {
        payload.api_key = form.api_key;
      }
      await updateAsset(activeAsset.id, payload);

      const models = await discoverAssetModels(activeAsset.id);
      setAvailableModels(models);
      setModelSearch("");
      setShowModelPicker(true);
      setMessage(`已获取模型：${models.length} 个`);
    } catch (err: any) {
      setMessage(err.message || "获取模型失败");
    }
  };

  const handlePickModel = async (modelId: string) => {
    if (!activeAsset) return;
    const models = _parseModels(form.models);
    if (models.includes(modelId)) {
      return;
    }
    const next = [...models, modelId];
    setForm({ ...form, models: next.join(", ") });
    try {
      const updated = await updateAsset(activeAsset.id, { models: next });
      setAssets((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("已添加模型");
    } catch (err: any) {
      setMessage(err.message || "添加模型失败");
    }
  };

  const handleImportAllModels = async () => {
    if (!activeAsset) return;
    const current = new Set(_parseModels(form.models));
    for (const item of availableModels) {
      current.add(item);
    }
    const next = Array.from(current);
    setForm({ ...form, models: next.join(", ") });
    try {
      const updated = await updateAsset(activeAsset.id, { models: next });
      setAssets((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setMessage(`已导入 ${next.length} 个模型`);
      setShowModelPicker(false);
    } catch (err: any) {
      setMessage(err.message || "导入失败");
    }
  };

  const handleCreate = async () => {
    try {
      const name = createForm.name.trim();
      if (!name) {
        setMessage("请输入名称");
        return;
      }
      const payload = {
        name,
        provider: createForm.provider,
        api_mode: createForm.api_mode,
        // Allow creating a provider first; user can set key/host later.
        api_key: "",
        base_url: null,
        api_path: null,
        models: []
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
    const supabase = getSupabaseClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
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
              setCreateForm({ name: "", provider: "OpenAI", api_mode: "openai_compatible" });
              setShowModal(true);
            }}
          >
            添加模型提供方
          </button>
        </header>

        {message ? <div className="notice">{message}</div> : null}
        {!hasConfig ? (
          <div className="notice">缺少 Supabase 配置，请检查环境变量。</div>
        ) : null}

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
                  <div className="hint">
                    已保存：{activeAsset.api_key_masked || "-"}（留空不修改）
                  </div>
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
                  <label>模型</label>
                  <div className="model-toolbar">
                    <input
                      placeholder="输入模型名称，例如 qwen-long-latest"
                      value={newModelName}
                      onChange={(e) => setNewModelName(e.target.value)}
                    />
                    <button className="ghost" type="button" onClick={handleAddModel}>
                      + 新建
                    </button>
                    <button className="ghost" type="button" onClick={handleFetchModels}>
                      获取模型
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    value={form.models}
                    onChange={(e) => setForm({ ...form, models: e.target.value })}
                  />
                  <div className="hint">逗号分隔；也可用上面的「新建 / 获取模型」</div>
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
                  <div className="book-date">
                    Tokens:{" "}
                    {(usageByBook[book.book_id]?.tokens_in || 0) +
                      (usageByBook[book.book_id]?.tokens_out || 0)}{" "}
                    (calls {usageByBook[book.book_id]?.calls || 0})
                  </div>
                </div>
              </div>
            ))
          )}
          </div>
        </section>
      </main>

      {showModal ? (
        <div className="modal-backdrop">
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">添加模型提供方</div>
            <div className="detail-row">
              <label>名称</label>
              <input
                value={createForm.name}
                onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              />
            </div>
            <div className="detail-row">
              <label>厂商</label>
              <select
                value={createForm.provider}
                onChange={(e) => setCreateForm({ ...createForm, provider: e.target.value })}
              >
                <option value="OpenAI">OpenAI</option>
                <option value="OpenRouter">OpenRouter</option>
                <option value="Azure OpenAI">Azure OpenAI</option>
                <option value="Claude">Claude</option>
                <option value="Gemini">Gemini</option>
                <option value="Qwen">Qwen</option>
                <option value="Moonshot">Moonshot</option>
                <option value="Groq">Groq</option>
              </select>
            </div>
            <div className="detail-row">
              <label>API 模式</label>
              <select
                value={createForm.api_mode}
                onChange={(e) => setCreateForm({ ...createForm, api_mode: e.target.value })}
              >
                <option value="openai_compatible">OpenAI API 兼容</option>
                <option value="native">原生</option>
              </select>
            </div>
            <div className="detail-actions">
              <button className="ghost" onClick={() => setShowModal(false)}>
                取消
              </button>
              <button className="primary" onClick={handleCreate}>
                添加
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showModelPicker ? (
        <div className="modal-backdrop">
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">编辑模型</div>
            <div className="detail-row">
              <label>搜索</label>
              <input
                placeholder="输入模型名称过滤..."
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
              />
            </div>
            <div className="model-list">
              {filteredAvailableModels.length === 0 ? (
                <div className="empty">没有匹配的模型</div>
              ) : (
                filteredAvailableModels.map((item) => (
                  <div key={item} className="model-item">
                    <div className="model-name">{item}</div>
                    <button
                      className="ghost"
                      type="button"
                      onClick={() => handlePickModel(item)}
                    >
                      +
                    </button>
                  </div>
                ))
              )}
            </div>
            <div className="detail-actions">
              <button className="ghost" onClick={() => setShowModelPicker(false)}>
                取消
              </button>
              <button className="primary" type="button" onClick={handleImportAllModels}>
                全部导入
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default dynamic(() => Promise.resolve(AccountPage), { ssr: false });
