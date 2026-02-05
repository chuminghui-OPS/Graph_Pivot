import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabase";

type Mode = "login" | "signup" | "reset";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    setMessage(null);
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/");
        return;
      }
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setMessage("注册成功，请检查邮箱完成验证或直接登录。");
        setMode("login");
        return;
      }
      if (mode === "reset") {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`
        });
        if (error) throw error;
        setMessage("重置邮件已发送，请查收邮箱。");
      }
    } catch (err: any) {
      setMessage(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-title">Graph Pivot</div>
        <div className="auth-subtitle">Supabase Auth 登录</div>
        <div className="auth-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
            type="button"
          >
            登录
          </button>
          <button
            className={mode === "signup" ? "active" : ""}
            onClick={() => setMode("signup")}
            type="button"
          >
            注册
          </button>
          <button
            className={mode === "reset" ? "active" : ""}
            onClick={() => setMode("reset")}
            type="button"
          >
            找回密码
          </button>
        </div>
        <div className="auth-field">
          <label>邮箱</label>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        {mode !== "reset" ? (
          <div className="auth-field">
            <label>密码</label>
            <input
              type="password"
              placeholder="至少 6 位"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
        ) : null}
        {message ? <div className="auth-message">{message}</div> : null}
        <button className="auth-primary" onClick={handleSubmit} disabled={loading}>
          {loading ? "处理中..." : mode === "login" ? "登录" : mode === "signup" ? "注册" : "发送邮件"}
        </button>
      </div>
    </div>
  );
}
