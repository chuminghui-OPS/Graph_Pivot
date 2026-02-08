import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { fetchPublicBooks, PublicBook } from "../lib/api";

export default function PublicBooksPage() {
  const router = useRouter();
  const [books, setBooks] = useState<PublicBook[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const data = await fetchPublicBooks(50, 0);
        if (mounted) setBooks(data);
      } catch (err: any) {
        if (mounted) setError(err.message || "加载失败");
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, []);

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
          <Link
            href="/public"
            className={`nav-link ${router.pathname === "/public" ? "active" : ""}`}
          >
            公共书库
          </Link>
          <Link href="/account" className="nav-link">
            个人中心
          </Link>
        </nav>
        <div className="topbar-actions">
          <div className="avatar-chip">U</div>
        </div>
      </header>

      <div className="page">
        <header className="hero">
          <div>
            <div className="title">公开书籍</div>
            <div className="subtitle">所有已发布的书籍列表</div>
          </div>
          <div className="upload-card">
            <div className="upload-title">去我的书籍</div>
            <Link href="/account" className="load-btn">
              个人中心
            </Link>
          </div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className="books-panel">
          <div className="panel-title">公开书籍</div>
          <div className="book-grid">
            {books.length === 0 ? (
              <div className="empty">暂无公开书籍</div>
            ) : (
              books.map((book) => (
                <div key={book.id} className="book-card">
                  <div className="book-cover">{book.title?.slice(0, 2) || "书"}</div>
                  <div className="book-info">
                    <div className="book-title">{book.title}</div>
                    <div className="book-id">{book.id}</div>
                    <div className="book-date">
                      收藏 {book.favorites_count} · 转发 {book.reposts_count}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
