import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import {
  fetchPublicBooks,
  fetchUserBooks,
  fetchUserProfile,
  PublicBook,
  UserBook,
  UserProfile,
  publishBook,
  unpublishBook
} from "../lib/api";

export default function PublicBooksPage() {
  const router = useRouter();
  const [books, setBooks] = useState<PublicBook[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [userBooks, setUserBooks] = useState<UserBook[]>([]);
  const [modalBook, setModalBook] = useState<{
    id: string;
    title: string;
    ownerUserId?: string | null;
    isPublic: boolean;
    favorites?: number;
    reposts?: number;
    publishedAt?: string | null;
  } | null>(null);
  const [modalMessage, setModalMessage] = useState<string | null>(null);
  const [modalBusy, setModalBusy] = useState(false);

  const publicBookIds = useMemo(() => new Set(books.map((book) => book.id)), [books]);

  const loadPublicBooks = async () => {
    const data = await fetchPublicBooks(50, 0);
    setBooks(data);
  };

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

  useEffect(() => {
    let mounted = true;
    const loadUser = async () => {
      try {
        const [profile, booksData] = await Promise.all([
          fetchUserProfile(),
          fetchUserBooks()
        ]);
        if (!mounted) return;
        setUserProfile(profile);
        setUserBooks(booksData);
      } catch {
        // ignore not authenticated
      }
    };
    loadUser();
    return () => {
      mounted = false;
    };
  }, []);

  const openPublicModal = (book: PublicBook) => {
    setModalMessage(null);
    setModalBook({
      id: book.id,
      title: book.title,
      ownerUserId: book.owner_user_id,
      isPublic: true,
      favorites: book.favorites_count,
      reposts: book.reposts_count,
      publishedAt: book.published_at
    });
  };

  const openUserModal = (book: UserBook) => {
    setModalMessage(null);
    setModalBook({
      id: book.book_id,
      title: book.title,
      ownerUserId: userProfile?.user_id,
      isPublic: publicBookIds.has(book.book_id),
      publishedAt: null
    });
  };

  const handlePublish = async (bookId: string) => {
    setModalBusy(true);
    setModalMessage(null);
    try {
      await publishBook(bookId);
      await loadPublicBooks();
      setModalBook((prev) => (prev ? { ...prev, isPublic: true } : prev));
      setModalMessage("已发布到公共书库");
    } catch (err: any) {
      setModalMessage(err.message || "发布失败");
    } finally {
      setModalBusy(false);
    }
  };

  const handleUnpublish = async (bookId: string) => {
    setModalBusy(true);
    setModalMessage(null);
    try {
      await unpublishBook(bookId);
      await loadPublicBooks();
      setModalBook((prev) => (prev ? { ...prev, isPublic: false } : prev));
      setModalMessage("已下架");
    } catch (err: any) {
      setModalMessage(err.message || "下架失败");
    } finally {
      setModalBusy(false);
    }
  };

  const isOwner =
    modalBook &&
    userProfile &&
    modalBook.ownerUserId &&
    modalBook.ownerUserId === userProfile.user_id;

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
            <Link href="/" className="load-btn">
              上传书籍
            </Link>
            <Link href="/account" className="load-btn">
              个人中心
            </Link>
          </div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        {userProfile ? (
          <section className="books-panel">
            <div className="panel-title">我的书籍</div>
            <div className="book-grid">
              {userBooks.length === 0 ? (
                <div className="empty">暂无书籍</div>
              ) : (
                userBooks.map((book) => {
                  const published = publicBookIds.has(book.book_id);
                  return (
                    <div
                      key={book.book_id}
                      className="book-card clickable"
                      onClick={() => openUserModal(book)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") openUserModal(book);
                      }}
                    >
                      <div className="book-cover">
                        {book.title?.slice(0, 2) || "书"}
                      </div>
                      <div className="book-info">
                        <div className="book-title">{book.title}</div>
                        <div className="book-id">{book.book_id}</div>
                        <div className={`book-status ${published ? "published" : "draft"}`}>
                          {published ? "已发布" : "未发布"}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>
        ) : null}

        <section className="books-panel">
          <div className="panel-title">公开书籍</div>
          <div className="book-grid">
            {books.length === 0 ? (
              <div className="empty">暂无公开书籍</div>
            ) : (
              books.map((book) => {
                const owner = userProfile?.user_id === book.owner_user_id;
                return (
                  <div
                    key={book.id}
                    className="book-card clickable"
                    onClick={() => router.push(`/?book_id=${book.id}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") router.push(`/?book_id=${book.id}`);
                    }}
                  >
                    <div className="book-cover">{book.title?.slice(0, 2) || "书"}</div>
                    <div className="book-info">
                      <div className="book-title">{book.title}</div>
                      <div className="book-id">{book.id}</div>
                      <div className="book-date">
                        收藏 {book.favorites_count} · 转发 {book.reposts_count}
                      </div>
                    </div>
                    {owner ? (
                      <div className="book-actions">
                        <button
                          className="ghost"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            openPublicModal(book);
                          }}
                        >
                          管理
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>

      {modalBook ? (
        <div className="modal-backdrop" onClick={() => setModalBook(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">{modalBook.title}</div>
            <div className="detail-row">
              <label>书籍 ID</label>
              <div className="hint">{modalBook.id}</div>
            </div>
            {modalBook.isPublic ? (
              <div className="detail-row">
                <label>公开数据</label>
                <div className="hint">
                  收藏 {modalBook.favorites || 0} · 转发 {modalBook.reposts || 0}
                </div>
              </div>
            ) : null}
            {modalMessage ? <div className="notice">{modalMessage}</div> : null}
            <div className="detail-actions">
              {isOwner ? (
                modalBook.isPublic ? (
                  <button
                    className="ghost danger"
                    type="button"
                    disabled={modalBusy}
                    onClick={() => handleUnpublish(modalBook.id)}
                  >
                    下架
                  </button>
                ) : (
                  <button
                    className="primary"
                    type="button"
                    disabled={modalBusy}
                    onClick={() => handlePublish(modalBook.id)}
                  >
                    发布到公共书库
                  </button>
                )
              ) : null}
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  router.push(`/?book_id=${modalBook.id}`);
                }}
              >
                查看图谱
              </button>
              <button className="ghost" type="button" onClick={() => setModalBook(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
