import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabase";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleReset = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      setMessage("密码已更新，请重新登录。");
      router.push("/login");
    } catch (err: any) {
      setMessage(err.message || "重置失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-title">重置密码</div>
        <div className="auth-field">
          <label>新密码</label>
          <input
            type="password"
            placeholder="至少 6 位"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        {message ? <div className="auth-message">{message}</div> : null}
        <button className="auth-primary" onClick={handleReset} disabled={loading}>
          {loading ? "处理中..." : "更新密码"}
        </button>
      </div>
    </div>
  );
}
