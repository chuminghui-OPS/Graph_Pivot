import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Graph } from "@antv/g6";
import type {
  GraphEdgeCreateInput,
  GraphEdgeUpdateInput,
  GraphNodeCreateInput,
  GraphNodeUpdateInput,
  KnowledgeGraph
} from "../lib/api";
import {
  createGraphEdge,
  createGraphNode,
  deleteGraphEdge,
  deleteGraphNode,
  updateGraphEdge,
  updateGraphNode
} from "../lib/api";

type GraphActionType = "node" | "edge";

export interface GraphActions {
  add: (type: GraphActionType, payload: GraphNodeCreateInput | GraphEdgeCreateInput) => Promise<void>;
  update: (
    type: GraphActionType,
    id: string,
    payload: GraphNodeUpdateInput | GraphEdgeUpdateInput
  ) => Promise<void>;
  removeItem: (type: GraphActionType, id: string) => Promise<void>;
}

interface EditEdgePayload {
  id: string;
  source: string;
  target: string;
  relation: string;
  evidence: string;
  confidence: number;
  source_text_location?: string | null;
}

interface GraphViewProps {
  bookId: string | null;
  graph: KnowledgeGraph | null;
  onSelectNode: (name: string) => void;
  onSelectEdge: (evidence: string) => void;
  onEditEdge?: (edge: EditEdgePayload) => void;
  onCreateEdge?: (payload: { source?: string }) => void;
  onGraphActions?: (actions: GraphActions | null) => void;
  onGraphChange?: (graph: KnowledgeGraph) => void;
}

type LodLevel = "hidden" | "simple" | "full";

export function GraphView({
  bookId,
  graph,
  onSelectNode,
  onSelectEdge,
  onEditEdge,
  onCreateEdge,
  onGraphActions,
  onGraphChange
}: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const lodLevelRef = useRef<LodLevel>("full");
  const graphSnapshotRef = useRef<KnowledgeGraph | null>(null);
  const [dims, setDims] = useState({ width: 300, height: 360 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const onSelectNodeRef = useRef(onSelectNode);
  const onSelectEdgeRef = useRef(onSelectEdge);
  const onEditEdgeRef = useRef(onEditEdge);
  const onCreateEdgeRef = useRef(onCreateEdge);

  const chapterId = graph?.chapter_id || graphSnapshotRef.current?.chapter_id || "";

  useEffect(() => {
    onSelectNodeRef.current = onSelectNode;
  }, [onSelectNode]);

  useEffect(() => {
    onSelectEdgeRef.current = onSelectEdge;
  }, [onSelectEdge]);

  useEffect(() => {
    onEditEdgeRef.current = onEditEdge;
  }, [onEditEdge]);

  useEffect(() => {
    onCreateEdgeRef.current = onCreateEdge;
  }, [onCreateEdge]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setDims({
        width: Math.max(280, Math.floor(entry.contentRect.width)),
        height: Math.max(360, Math.floor(entry.contentRect.height))
      });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const resolveNodeNameById = (id: string) => {
    const snapshot = graphSnapshotRef.current;
    if (!snapshot) return id;
    const node = snapshot.nodes.find((item) => item.id === id);
    return node?.name || id;
  };

  const resolveEdgePayload = (edgeId: string): EditEdgePayload | null => {
    const graphInstance = graphRef.current;
    if (!graphInstance) return null;
    const edgeData = graphInstance.getEdgeData(edgeId);
    const data = (edgeData as any)?.data || {};
    const sourceId = String((edgeData as any)?.source ?? "");
    const targetId = String((edgeData as any)?.target ?? "");
    const sourceName = data.sourceName || resolveNodeNameById(sourceId);
    const targetName = data.targetName || resolveNodeNameById(targetId);
    return {
      id: String(edgeData.id ?? edgeId),
      source: sourceName,
      target: targetName,
      relation: String(data.relation ?? ""),
      evidence: String(data.evidence ?? ""),
      confidence: Number.isFinite(data.confidence) ? Number(data.confidence) : 0.5,
      source_text_location: data.source_text_location ?? null
    };
  };

  const readZoom = (evt?: { data?: { scale?: number } }) => {
    if (typeof evt?.data?.scale === "number") {
      return evt.data.scale;
    }
    const graphInstance = graphRef.current;
    if (!graphInstance) return undefined;
    try {
      const zoom = (graphInstance as any).getZoom?.();
      return typeof zoom === "number" ? zoom : undefined;
    } catch {
      return undefined;
    }
  };

  const toG6Data = (kg: KnowledgeGraph | null) => {
    if (!kg) return { nodes: [], edges: [] };
    const nameToId = new Map(kg.nodes.map((node) => [node.name, node.id]));
    return {
      nodes: kg.nodes.map((node) => ({
        id: node.id,
        data: {
          name: node.name,
          type: node.type,
          labelSimple: node.name,
          labelFull: `${node.name} (${node.type})`,
          lod: "full"
        }
      })),
      edges: kg.edges.map((edge, index) => {
        const sourceId = nameToId.get(edge.source) || edge.source;
        const targetId = nameToId.get(edge.target) || edge.target;
        return {
          id: edge.id || `${edge.source}-${edge.target}-${index}`,
          source: sourceId,
          target: targetId,
          data: {
            relation: edge.relation,
            evidence: edge.evidence,
            confidence: edge.confidence,
            source_text_location: edge.source_text_location ?? null,
            sourceName: edge.source,
            targetName: edge.target
          }
        };
      })
    };
  };

  const applyLodLevel = (next: LodLevel) => {
    const graphInstance = graphRef.current;
    if (!graphInstance) return;
    const nodes = graphInstance.getNodeData();
    graphInstance.updateNodeData(
      nodes.map((node: any) => ({
        id: node.id,
        data: { ...(node.data || {}), lod: next }
      }))
    );
    graphInstance.draw();
  };

  useEffect(() => {
    graphSnapshotRef.current = graph;
  }, [graph]);

  useEffect(() => {
    let cancelled = false;
    const initGraph = async () => {
      if (!containerRef.current) return;
      if (graphRef.current) return;
      const [{ Graph: G6Graph, GraphEvent }, { Renderer }] = await Promise.all([
        import("@antv/g6"),
        import("@antv/g-canvas")
      ]);
      if (cancelled) return;
      const graphInstance = new G6Graph({
        container: containerRef.current,
        width: dims.width,
        height: dims.height,
        renderer: () => new Renderer(),
        data: toG6Data(graphSnapshotRef.current || graph),
        layout: {
          type: "force",
          enableWorker: true
        },
        node: {
          type: "rect",
          style: {
            size: [150, 46],
            radius: 12,
            fill: "#ffffff",
            stroke: "#e2e8f0",
            lineWidth: 1,
            shadowColor: "rgba(15, 23, 42, 0.08)",
            shadowBlur: 12,
            shadowOffsetX: 0,
            shadowOffsetY: 6,
            label: (d: any) => d.data?.lod !== "hidden",
            labelText: (d: any) =>
              d.data?.lod === "full" ? d.data?.labelFull : d.data?.labelSimple,
            labelPlacement: "center",
            labelFill: "#1f2937",
            labelFontSize: 12,
            labelWordWrap: true,
            labelMaxWidth: 130,
            labelLineHeight: 14
          }
        },
        edge: {
          type: "line",
          style: {
            stroke: "#94a3b8",
            lineWidth: 1,
            endArrow: true,
            endArrowType: "triangle",
            endArrowSize: 8,
            endArrowFill: "#94a3b8",
            labelText: (d: any) => d.data?.relation || "",
            labelFontSize: 10,
            labelFill: "#64748b",
            labelPlacement: "center",
            labelAutoRotate: true
          }
        },
        behaviors: ["drag-canvas", "zoom-canvas", "drag-element"],
        plugins: [
          {
            key: "contextmenu",
            type: "contextmenu",
            trigger: "contextmenu",
            getItems: (event: any) => {
              const targetType = event?.targetType;
              if (targetType === "node") {
                return [
                  { name: "新增节点", value: "add-node" },
                  { name: "创建关系", value: "add-edge" },
                  { name: "编辑节点", value: "edit-node" },
                  { name: "删除节点", value: "remove-node" }
                ];
              }
              if (targetType === "edge") {
                return [
                  { name: "编辑关系", value: "edit-edge" },
                  { name: "删除关系", value: "remove-edge" }
                ];
              }
              return [];
            },
            onClick: async (value: string, _target: HTMLElement, current: any) => {
              const id = current?.id;
              if (!id || !graphInstance) return;
              const isNode = graphInstance.hasNode(id);
              const isEdge = graphInstance.hasEdge(id);
              if (value === "add-node" && isNode) {
                const name = window.prompt("节点名称");
                if (!name) return;
                const type = window.prompt("节点类型", "Concept") || "Concept";
                await actionsRef.current?.add("node", { name, type });
              }
              if (value === "add-edge" && isNode) {
                const node = graphInstance.getNodeData(id);
                const sourceName = String((node as any)?.data?.name || "");
                if (onCreateEdgeRef.current) {
                  onCreateEdgeRef.current({ source: sourceName || undefined });
                }
              }
              if (value === "edit-node" && isNode) {
                const node = graphInstance.getNodeData(id);
                const nextName =
                  window.prompt("节点名称", String((node as any)?.data?.name || "")) ||
                  "";
                if (!nextName) return;
                const nextType =
                  window.prompt("节点类型", String((node as any)?.data?.type || "Concept")) ||
                  "Concept";
                await actionsRef.current?.update("node", String(node.id), {
                  name: nextName,
                  type: nextType
                });
              }
              if (value === "remove-node" && isNode) {
                await actionsRef.current?.removeItem("node", String(id));
              }
              if (value === "edit-edge" && isEdge) {
                const payload = resolveEdgePayload(String(id));
                if (payload && onEditEdgeRef.current) {
                  onEditEdgeRef.current(payload);
                }
              }
              if (value === "remove-edge" && isEdge) {
                await actionsRef.current?.removeItem("edge", String(id));
              }
            }
          }
        ]
      });

      graphInstance.on("node:click", (evt: any) => {
        const id = evt?.target?.id;
        if (!id) return;
        const node = graphInstance.getNodeData(id);
        const name = String((node as any)?.data?.name || "");
        if (name) onSelectNodeRef.current(name);
      });

      graphInstance.on("edge:click", (evt: any) => {
        const id = evt?.target?.id;
        if (!id) return;
        const edge = graphInstance.getEdgeData(id);
        const evidence = String((edge as any)?.data?.evidence || "");
        if (evidence) onSelectEdgeRef.current(evidence);
      });

      graphInstance.on(GraphEvent.AFTER_TRANSFORM, (evt: any) => {
        const zoom = readZoom(evt);
        if (typeof zoom !== "number") return;
        const nextLevel: LodLevel =
          zoom < 0.5 ? "hidden" : zoom > 0.8 ? "full" : "simple";
        if (lodLevelRef.current !== nextLevel) {
          lodLevelRef.current = nextLevel;
          applyLodLevel(nextLevel);
        }
      });

      graphRef.current = graphInstance;
      (graphInstance as any).render?.();
      graphInstance.fitView?.();
    };
    initGraph();
    return () => {
      cancelled = true;
      graphRef.current?.destroy();
      graphRef.current = null;
      onGraphActions?.(null);
    };
  }, []);

  useEffect(() => {
    const graphInstance = graphRef.current;
    if (!graphInstance) return;
    graphInstance.setSize(dims.width, dims.height);
    graphInstance.draw();
  }, [dims.width, dims.height]);

  useEffect(() => {
    const graphInstance = graphRef.current;
    if (!graphInstance) return;
    graphInstance.setData(toG6Data(graph));
    graphInstance.draw();
    lodLevelRef.current = "full";
    applyLodLevel("full");
  }, [graph]);

  const updateGraphSnapshot = useCallback(
    (next: KnowledgeGraph) => {
      graphSnapshotRef.current = next;
      onGraphChange?.(next);
      const graphInstance = graphRef.current;
      if (graphInstance) {
        graphInstance.setData(toG6Data(next));
        graphInstance.draw();
      }
    },
    [onGraphChange]
  );

  const actionsRef = useRef<GraphActions | null>(null);

  const actions = useMemo<GraphActions>(() => {
    return {
      add: async (type, payload) => {
        if (!bookId || !chapterId) return;
        if (type === "node") {
          const created = await createGraphNode(
            bookId,
            chapterId,
            payload as GraphNodeCreateInput
          );
          const next: KnowledgeGraph = {
            chapter_id: chapterId,
            nodes: [...(graphSnapshotRef.current?.nodes || []), created],
            edges: [...(graphSnapshotRef.current?.edges || [])]
          };
          updateGraphSnapshot(next);
        } else {
          const created = await createGraphEdge(
            bookId,
            chapterId,
            payload as GraphEdgeCreateInput
          );
          const next: KnowledgeGraph = {
            chapter_id: chapterId,
            nodes: [...(graphSnapshotRef.current?.nodes || [])],
            edges: [...(graphSnapshotRef.current?.edges || []), created]
          };
          updateGraphSnapshot(next);
        }
      },
      update: async (type, id, payload) => {
        if (!bookId || !chapterId) return;
        if (type === "node") {
          const updated = await updateGraphNode(
            bookId,
            chapterId,
            id,
            payload as GraphNodeUpdateInput
          );
          const prevNodes = graphSnapshotRef.current?.nodes || [];
          const prev = prevNodes.find((node) => node.id === id);
          const nextNodes = prevNodes.map((node) =>
            node.id === id ? updated : node
          );
          let nextEdges = graphSnapshotRef.current?.edges || [];
          if (prev && prev.name !== updated.name) {
            nextEdges = nextEdges.map((edge) => ({
              ...edge,
              source: edge.source === prev.name ? updated.name : edge.source,
              target: edge.target === prev.name ? updated.name : edge.target
            }));
          }
          updateGraphSnapshot({
            chapter_id: chapterId,
            nodes: nextNodes,
            edges: nextEdges
          });
        } else {
          const updated = await updateGraphEdge(
            bookId,
            chapterId,
            id,
            payload as GraphEdgeUpdateInput
          );
          const nextEdges = (graphSnapshotRef.current?.edges || []).map((edge) =>
            edge.id === id ? updated : edge
          );
          updateGraphSnapshot({
            chapter_id: chapterId,
            nodes: [...(graphSnapshotRef.current?.nodes || [])],
            edges: nextEdges
          });
        }
      },
      removeItem: async (type, id) => {
        if (!bookId || !chapterId) return;
        if (type === "node") {
          await deleteGraphNode(bookId, chapterId, id);
          const nodes = (graphSnapshotRef.current?.nodes || []).filter(
            (node) => node.id !== id
          );
          const removed = graphSnapshotRef.current?.nodes.find((node) => node.id === id);
          const edges = removed
            ? (graphSnapshotRef.current?.edges || []).filter(
                (edge) => edge.source !== removed.name && edge.target !== removed.name
              )
            : [...(graphSnapshotRef.current?.edges || [])];
          updateGraphSnapshot({ chapter_id: chapterId, nodes, edges });
        } else {
          await deleteGraphEdge(bookId, chapterId, id);
          const edges = (graphSnapshotRef.current?.edges || []).filter(
            (edge) => edge.id !== id
          );
          updateGraphSnapshot({
            chapter_id: chapterId,
            nodes: [...(graphSnapshotRef.current?.nodes || [])],
            edges
          });
        }
      }
    };
  }, [bookId, chapterId, updateGraphSnapshot]);

  useEffect(() => {
    actionsRef.current = actions;
    onGraphActions?.(actions);
  }, [actions, onGraphActions]);

  return (
    <div className={`panel graph-panel ${isFullscreen ? "fullscreen" : ""}`}>
      <div className="panel-title">
        <span>Chapter Graph</span>
      </div>
      <button
        className="graph-fullscreen-btn"
        type="button"
        aria-label={isFullscreen ? "exit fullscreen" : "enter fullscreen"}
        onClick={() => setIsFullscreen((prev) => !prev)}
      >
        {isFullscreen ? "×" : "⤢"}
      </button>
      <div className="graph-canvas g6-canvas" ref={containerRef} />
    </div>
  );
}
