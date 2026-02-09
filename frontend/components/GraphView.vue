<template>
  <div class="panel graph-panel" :class="{ fullscreen: isFullscreen }">
    <div class="panel-title">
      <span>Chapter Graph</span>
    </div>
    <button
      class="graph-fullscreen-btn"
      type="button"
      :aria-label="isFullscreen ? 'exit fullscreen' : 'enter fullscreen'"
      @click="toggleFullscreen"
    >
      {{ isFullscreen ? "×" : "⤢" }}
    </button>
    <div ref="containerRef" class="graph-canvas g6-canvas" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
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

const props = defineProps<{
  bookId: string | null;
  graph: KnowledgeGraph | null;
}>();

const emit = defineEmits<{
  (e: "select-node", name: string): void;
  (e: "select-edge", evidence: string): void;
  (e: "edit-edge", edge: EditEdgePayload): void;
  (e: "create-edge", payload: { source?: string }): void;
  (e: "graph-actions", actions: GraphActions | null): void;
  (e: "graph-change", graph: KnowledgeGraph): void;
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const graphRef = ref<Graph | null>(null);
const graphSnapshot = ref<KnowledgeGraph | null>(null);
const isFullscreen = ref(false);
const lodLevel = ref<"hidden" | "simple" | "full">("full");

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

const resolveNodeNameById = (id: string) => {
  const snapshot = graphSnapshot.value;
  if (!snapshot) return id;
  const node = snapshot.nodes.find((item) => item.id === id);
  return node?.name || id;
};

const resolveEdgePayload = (edgeId: string): EditEdgePayload | null => {
  const graphInstance = graphRef.value;
  if (!graphInstance) return null;
  const edgeData = graphInstance.getEdgeData(edgeId) as any;
  const data = edgeData?.data || {};
  const sourceId = String(edgeData?.source ?? "");
  const targetId = String(edgeData?.target ?? "");
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

const applyLodLevel = (next: "hidden" | "simple" | "full") => {
  const graphInstance = graphRef.value;
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

const updateGraphSnapshot = (next: KnowledgeGraph) => {
  graphSnapshot.value = next;
  emit("graph-change", next);
  const graphInstance = graphRef.value;
  if (graphInstance) {
    graphInstance.setData(toG6Data(next));
    graphInstance.draw();
  }
};

const chapterId = () =>
  props.graph?.chapter_id || graphSnapshot.value?.chapter_id || "";

const actions: GraphActions = {
  add: async (type, payload) => {
    if (!props.bookId || !chapterId()) return;
    if (type === "node") {
      const created = await createGraphNode(
        props.bookId,
        chapterId(),
        payload as GraphNodeCreateInput
      );
      updateGraphSnapshot({
        chapter_id: chapterId(),
        nodes: [...(graphSnapshot.value?.nodes || []), created],
        edges: [...(graphSnapshot.value?.edges || [])]
      });
    } else {
      const created = await createGraphEdge(
        props.bookId,
        chapterId(),
        payload as GraphEdgeCreateInput
      );
      updateGraphSnapshot({
        chapter_id: chapterId(),
        nodes: [...(graphSnapshot.value?.nodes || [])],
        edges: [...(graphSnapshot.value?.edges || []), created]
      });
    }
  },
  update: async (type, id, payload) => {
    if (!props.bookId || !chapterId()) return;
    if (type === "node") {
      const updated = await updateGraphNode(
        props.bookId,
        chapterId(),
        id,
        payload as GraphNodeUpdateInput
      );
      const prevNodes = graphSnapshot.value?.nodes || [];
      const prev = prevNodes.find((node) => node.id === id);
      const nextNodes = prevNodes.map((node) => (node.id === id ? updated : node));
      let nextEdges = graphSnapshot.value?.edges || [];
      if (prev && prev.name !== updated.name) {
        nextEdges = nextEdges.map((edge) => ({
          ...edge,
          source: edge.source === prev.name ? updated.name : edge.source,
          target: edge.target === prev.name ? updated.name : edge.target
        }));
      }
      updateGraphSnapshot({
        chapter_id: chapterId(),
        nodes: nextNodes,
        edges: nextEdges
      });
    } else {
      const updated = await updateGraphEdge(
        props.bookId,
        chapterId(),
        id,
        payload as GraphEdgeUpdateInput
      );
      const nextEdges = (graphSnapshot.value?.edges || []).map((edge) =>
        edge.id === id ? updated : edge
      );
      updateGraphSnapshot({
        chapter_id: chapterId(),
        nodes: [...(graphSnapshot.value?.nodes || [])],
        edges: nextEdges
      });
    }
  },
  removeItem: async (type, id) => {
    if (!props.bookId || !chapterId()) return;
    if (type === "node") {
      await deleteGraphNode(props.bookId, chapterId(), id);
      const nodes = (graphSnapshot.value?.nodes || []).filter((node) => node.id !== id);
      const removed = graphSnapshot.value?.nodes.find((node) => node.id === id);
      const edges = removed
        ? (graphSnapshot.value?.edges || []).filter(
            (edge) => edge.source !== removed.name && edge.target !== removed.name
          )
        : [...(graphSnapshot.value?.edges || [])];
      updateGraphSnapshot({ chapter_id: chapterId(), nodes, edges });
    } else {
      await deleteGraphEdge(props.bookId, chapterId(), id);
      const edges = (graphSnapshot.value?.edges || []).filter((edge) => edge.id !== id);
      updateGraphSnapshot({
        chapter_id: chapterId(),
        nodes: [...(graphSnapshot.value?.nodes || [])],
        edges
      });
    }
  }
};

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value;
};

onMounted(async () => {
  if (!containerRef.value) return;
  const [{ Graph: G6Graph, GraphEvent }, { Renderer }] = await Promise.all([
    import("@antv/g6"),
    import("@antv/g-canvas")
  ]);
  const graphInstance = new G6Graph({
    container: containerRef.value,
    renderer: () => new Renderer(),
    data: toG6Data(graphSnapshot.value || props.graph),
    layout: { type: "force", enableWorker: true },
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
          if (!id) return;
          const isNode = graphInstance.hasNode(id);
          const isEdge = graphInstance.hasEdge(id);
          if (value === "add-node" && isNode) {
            const name = window.prompt("节点名称");
            if (!name) return;
            const type = window.prompt("节点类型", "Concept") || "Concept";
            await actions.add("node", { name, type });
          }
          if (value === "add-edge" && isNode) {
            const node = graphInstance.getNodeData(id) as any;
            const sourceName = String(node?.data?.name || "");
            emit("create-edge", { source: sourceName || undefined });
          }
          if (value === "edit-node" && isNode) {
            const node = graphInstance.getNodeData(id) as any;
            const nextName = window.prompt("节点名称", String(node?.data?.name || "")) || "";
            if (!nextName) return;
            const nextType =
              window.prompt("节点类型", String(node?.data?.type || "Concept")) || "Concept";
            await actions.update("node", String(node.id), { name: nextName, type: nextType });
          }
          if (value === "remove-node" && isNode) {
            await actions.removeItem("node", String(id));
          }
          if (value === "edit-edge" && isEdge) {
            const payload = resolveEdgePayload(String(id));
            if (payload) emit("edit-edge", payload);
          }
          if (value === "remove-edge" && isEdge) {
            await actions.removeItem("edge", String(id));
          }
        }
      }
    ]
  });

  graphInstance.on("node:click", (evt: any) => {
    const id = evt?.target?.id;
    if (!id) return;
    const node = graphInstance.getNodeData(id) as any;
    const name = String(node?.data?.name || "");
    if (name) emit("select-node", name);
  });

  graphInstance.on("edge:click", (evt: any) => {
    const id = evt?.target?.id;
    if (!id) return;
    const edge = graphInstance.getEdgeData(id) as any;
    const evidence = String(edge?.data?.evidence || "");
    if (evidence) emit("select-edge", evidence);
  });

  graphInstance.on(GraphEvent.AFTER_TRANSFORM, () => {
    const zoom = graphInstance.getZoom();
    const nextLevel = zoom < 0.5 ? "hidden" : zoom > 0.8 ? "full" : "simple";
    if (lodLevel.value !== nextLevel) {
      lodLevel.value = nextLevel;
      applyLodLevel(nextLevel);
    }
  });

  graphRef.value = graphInstance;
  (graphInstance as any).render?.();
  graphInstance.fitView?.({ padding: 30 });
  emit("graph-actions", actions);

  const resizeObserver = new ResizeObserver((entries) => {
    const entry = entries[0];
    if (!entry || !graphRef.value) return;
    const width = Math.max(280, Math.floor(entry.contentRect.width));
    const height = Math.max(360, Math.floor(entry.contentRect.height));
    graphRef.value.setSize(width, height);
    graphRef.value.draw();
  });
  if (containerRef.value) {
    resizeObserver.observe(containerRef.value);
  }

  onBeforeUnmount(() => {
    resizeObserver.disconnect();
  });
});

watch(
  () => props.graph,
  (next) => {
    graphSnapshot.value = next || null;
    if (graphRef.value) {
      graphRef.value.setData(toG6Data(next || null));
      graphRef.value.draw();
      lodLevel.value = "full";
      applyLodLevel("full");
    }
  }
);

onBeforeUnmount(() => {
  graphRef.value?.destroy();
  graphRef.value = null;
  emit("graph-actions", null);
});
</script>
