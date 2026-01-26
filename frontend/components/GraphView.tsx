import dynamic from "next/dynamic";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { KnowledgeGraph } from "../lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false
});

interface GraphViewProps {
  graph: KnowledgeGraph | null;
  onSelectNode: (name: string) => void;
  onSelectEdge: (evidence: string) => void;
}

export function GraphView({ graph, onSelectNode, onSelectEdge }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fgRef = useRef<any>(null);
  const [dims, setDims] = useState({ width: 300, height: 360 });

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

  const data = useMemo(() => {
    if (!graph) {
      return { nodes: [], links: [] };
    }
    const nameToId = new Map(
      graph.nodes.map((node) => [node.name, node.id])
    );
    const links = graph.edges.map((edge, index) => ({
      id: `${edge.source}-${edge.target}-${index}`,
      source: nameToId.get(edge.source) || edge.source,
      target: nameToId.get(edge.target) || edge.target,
      relation: edge.relation,
      evidence: edge.evidence
    }));
    return {
      nodes: graph.nodes.map((node) => ({
        id: node.id,
        name: node.name,
        type: node.type
      })),
      links
    };
  }, [graph]);

  useEffect(() => {
    if (!fgRef.current) return;
    if (!data.nodes.length) return;
    if (typeof fgRef.current.zoomToFit === "function") {
      fgRef.current.zoomToFit(400, 30);
    }
  }, [data.nodes.length, data.links.length, dims.width, dims.height]);

  return (
    <div className="panel graph-panel">
      <div className="panel-title">Chapter Graph</div>
      <div className="graph-canvas" ref={containerRef}>
        {dims.width > 0 && dims.height > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            key={`${graph?.chapter_id ?? "empty"}-${data.nodes.length}-${data.links.length}`}
            graphData={data}
            width={dims.width}
            height={dims.height}
            cooldownTicks={100}
            nodeLabel={(node: any) => `${node.name} (${node.type})`}
            nodeColor={(node: any) =>
              node.type?.toLowerCase().includes("concept")
                ? "#2f6f6d"
                : "#c9782c"
            }
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const label = String(node.name ?? "");
              if (!label) return;
              const fontSize = Math.max(6, 10 / globalScale);
              ctx.font = `${fontSize}px "Space Grotesk", sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "#1f1d1a";
              ctx.fillText(label, node.x, node.y - 10 / globalScale);
            }}
            nodeCanvasObjectMode={() => "after"}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            linkLabel={(link: any) => link.relation}
            linkCanvasObject={(link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const label = String(link.relation ?? "");
              if (!label) return;
              const start = link.source;
              const end = link.target;
              if (!start || !end) return;
              const x = (start.x + end.x) / 2;
              const y = (start.y + end.y) / 2;
              const fontSize = Math.max(4, 6 / globalScale);
              ctx.font = `${fontSize}px "Space Grotesk", sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "#6f6a63";
              ctx.fillText(label, x, y);
            }}
            linkCanvasObjectMode={() => "after"}
            onNodeClick={(node: any) => onSelectNode(node.name)}
            onLinkClick={(link: any) => onSelectEdge(link.evidence)}
            backgroundColor="transparent"
            onEngineStop={() => fgRef.current?.zoomToFit?.(400, 30)}
          />
        ) : null}
      </div>
    </div>
  );
}
