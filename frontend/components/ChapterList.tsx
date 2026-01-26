import React from "react";
import { Chapter, ChapterStatus } from "../lib/api";

const statusClass: Record<ChapterStatus, string> = {
  PENDING: "status status-pending",
  PROCESSING: "status status-processing",
  DONE: "status status-done",
  FAILED: "status status-failed",
  SKIPPED_TOO_LARGE: "status status-failed",
  TIMEOUT: "status status-failed",
  PAUSED: "status status-pending"
};

const statusLabel: Record<ChapterStatus, string> = {
  PENDING: "等待中",
  PROCESSING: "处理中",
  DONE: "完成",
  FAILED: "失败",
  SKIPPED_TOO_LARGE: "已跳过",
  TIMEOUT: "超时",
  PAUSED: "已暂停"
};

interface ChapterListProps {
  chapters: Chapter[];
  activeId: string | null;
  onSelect: (chapterId: string) => void;
}

export function ChapterList({ chapters, activeId, onSelect }: ChapterListProps) {
  return (
    <div className="panel">
      <div className="panel-title">Chapters</div>
      <div className="chapter-list">
        {chapters.map((chapter) => (
          <button
            key={chapter.chapter_id}
            className={`chapter-item ${
              activeId === chapter.chapter_id ? "active" : ""
            }`}
            onClick={() => onSelect(chapter.chapter_id)}
          >
            <div className="chapter-meta">
              <span className="chapter-title">{chapter.title}</span>
              <span className={statusClass[chapter.status]}>
                {statusLabel[chapter.status]}
              </span>
            </div>
            {chapter.status === "SKIPPED_TOO_LARGE" ? (
              <div className="chapter-note">
                该章节内容过多，无法使用 Gemini 加载，已跳过
              </div>
            ) : null}
            {chapter.status === "TIMEOUT" ? (
              <div className="chapter-note">该章节处理超时</div>
            ) : null}
            {chapter.status === "PAUSED" ? (
              <div className="chapter-note">该书未在前台查看，已暂停处理</div>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
