import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  FileText,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Info,
  Layers,
  RotateCcw,
  RefreshCw,
  Search,
  CheckCircle2,
  Columns
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import { getHeaders, getDocumentDetails } from '../services/api';
import { ExtractedFieldItem } from '../types';

// Set up PDF.js worker
if (typeof window !== 'undefined' && 'Worker' in window) {
  try {
    pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.mjs',
      import.meta.url
    ).toString();
  } catch {
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;
  }
}

export interface BoundingBoxCoords {
  x: number;
  y: number;
  width: number;
  height: number;
  page_width: number;
  page_height: number;
}

export interface DocumentViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentTitle: string;
  categoryCode?: string;
  streamUrl: string;
  mimeType?: string;
  pageCount?: number;
  initialPage?: number;
  extractedText?: string | null;
  verificationSource?: string | null;
  verificationStatus?: string | null;
  verificationEvidence?: string | null;
  supportingSnippet?: string | null;
  documentId?: number | null;
  boundingBox?: string | null;
  // Cross-document comparison support
  secondaryDocumentId?: number | null;
  secondaryDocumentName?: string | null;
  secondaryPageNumber?: number | null;
  secondaryStreamUrl?: string | null;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  isOpen,
  onClose,
  documentTitle,
  categoryCode,
  streamUrl,
  mimeType = 'application/pdf',
  pageCount = 1,
  initialPage = 1,
  extractedText: initialExtractedText,
  verificationSource,
  verificationStatus,
  verificationEvidence,
  supportingSnippet,
  documentId: initialDocumentId,
  boundingBox: initialBoundingBox,
  secondaryDocumentId,
  secondaryDocumentName,
  secondaryPageNumber,
  secondaryStreamUrl,
}) => {
  // Document selection (Primary vs Secondary comparison document)
  const [activeTab, setActiveTab] = useState<'PRIMARY' | 'SECONDARY'>('PRIMARY');

  const activeDocId = activeTab === 'PRIMARY' ? initialDocumentId : secondaryDocumentId;
  const activeStreamUrl = activeTab === 'PRIMARY' ? streamUrl : (secondaryStreamUrl || streamUrl);
  const activeTitle = activeTab === 'PRIMARY' ? documentTitle : (secondaryDocumentName || 'Comparison Document');
  const targetPage = activeTab === 'PRIMARY' ? (initialPage || 1) : (secondaryPageNumber || 1);

  // Viewer state
  const [currentPage, setCurrentPage] = useState<number>(targetPage);
  const [totalPages, setTotalPages] = useState<number>(pageCount || 1);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [fitToWidth, setFitToWidth] = useState<boolean>(false);
  const [useNativeViewer, setUseNativeViewer] = useState<boolean>(false);
  const [showMetadataPanel, setShowMetadataPanel] = useState<boolean>(true);

  // Fetch & rendering state
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<{ title: string; detail: string; status?: number } | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [pdfDocProxy, setPdfDocProxy] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  // Extracted data state
  const [extractedFields, setExtractedFields] = useState<ExtractedFieldItem[]>([]);
  const [extractedTextContent, setExtractedTextContent] = useState<string | null>(initialExtractedText || null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);

  // Canvas ref for PDF rendering
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<any>(null);

  // Reset tab on open
  useEffect(() => {
    if (isOpen) {
      setActiveTab('PRIMARY');
      setCurrentPage(initialPage && initialPage > 0 ? initialPage : 1);
      setFetchError(null);
      setRenderError(null);
      setZoomLevel(100);
      setFitToWidth(false);
    }
  }, [isOpen, initialPage, streamUrl]);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Fetch document details (extracted fields, metadata) from backend
  useEffect(() => {
    if (!isOpen || !activeDocId) return;

    let isMounted = true;
    setLoadingDetails(true);

    getDocumentDetails(activeDocId)
      .then((data) => {
        if (!isMounted) return;
        if (data.extracted_fields) {
          setExtractedFields(data.extracted_fields);
        }
        if (data.extracted_text) {
          setExtractedTextContent(data.extracted_text);
        }
        if (data.page_count && data.page_count > 1) {
          setTotalPages(data.page_count);
        }
      })
      .catch(() => {
        // Fallback to initial values if detail fetch fails
      })
      .finally(() => {
        if (isMounted) setLoadingDetails(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, activeDocId]);

  // Fetch binary document stream safely with auth headers
  const fetchDocumentBlob = useCallback(async () => {
    if (!activeStreamUrl) {
      setFetchError({
        title: 'Document URL Missing',
        detail: 'No valid retrieval endpoint was provided for this attachment.',
      });
      setLoading(false);
      return;
    }

    setLoading(true);
    setFetchError(null);
    setRenderError(null);

    try {
      const response = await fetch(activeStreamUrl, {
        headers: getHeaders(),
      });

      if (!response.ok) {
        let errMessage = 'Document could not be retrieved from the AICTE secure vault.';
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errMessage = errData.detail;
          }
        } catch {
          errMessage = `Server returned status HTTP ${response.status}: ${response.statusText}`;
        }
        setFetchError({
          title: response.status === 404 ? 'Document Not Found in Vault' : 'Document Retrieval Error',
          detail: errMessage,
          status: response.status,
        });
        setLoading(false);
        return;
      }

      const contentType = response.headers.get('content-type') || '';
      // Guard against JSON API errors disguised as 200
      if (contentType.includes('application/json')) {
        const jsonData = await response.json();
        setFetchError({
          title: 'Unexpected Response Format',
          detail: jsonData.detail || 'The vault returned API metadata instead of the expected binary stream.',
        });
        setLoading(false);
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setBlobUrl(url);

      // Determine document type
      const isPdfDoc =
        contentType.includes('pdf') ||
        activeTitle.toLowerCase().endsWith('.pdf') ||
        activeStreamUrl.toLowerCase().includes('pdf');

      if (isPdfDoc) {
        try {
          const arrayBuffer = await blob.arrayBuffer();
          const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
          const pdfDoc = await loadingTask.promise;
          setPdfDocProxy(pdfDoc);
          setTotalPages(pdfDoc.numPages);
        } catch (pdfErr: any) {
          console.warn('PDF.js parse warning, enabling native viewer fallback:', pdfErr);
          setUseNativeViewer(true);
        }
      }
    } catch (netErr: any) {
      setFetchError({
        title: 'Network Communication Error',
        detail: netErr.message || 'Failed to establish connection to AICTE document server.',
      });
    } finally {
      setLoading(false);
    }
  }, [activeStreamUrl, activeTitle]);

  // Trigger fetch on streamUrl or activeTab change
  useEffect(() => {
    if (isOpen) {
      fetchDocumentBlob();
    }
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [isOpen, activeTab, fetchDocumentBlob]);

  // Render PDF page to canvas when page, zoom or pdfDocProxy changes
  useEffect(() => {
    if (!pdfDocProxy || useNativeViewer) return;

    let isCancelled = false;

    const renderPage = async () => {
      try {
        const pageIndex = Math.min(Math.max(currentPage, 1), pdfDocProxy.numPages);
        const page = await pdfDocProxy.getPage(pageIndex);
        if (isCancelled) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const baseViewport = page.getViewport({ scale: 1.0 });

        let scale = zoomLevel / 100;
        if (fitToWidth && canvas.parentElement) {
          const containerWidth = canvas.parentElement.clientWidth - 48;
          if (containerWidth > 0) {
            scale = containerWidth / baseViewport.width;
          }
        }

        const viewport = page.getViewport({ scale });
        const pixelRatio = window.devicePixelRatio || 1;

        canvas.width = viewport.width * pixelRatio;
        canvas.height = viewport.height * pixelRatio;
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

        if (renderTaskRef.current) {
          try {
            renderTaskRef.current.cancel();
          } catch {}
        }

        renderTaskRef.current = page.render({
          canvas: canvas,
          canvasContext: ctx,
          viewport: viewport,
        });

        await renderTaskRef.current.promise;
      } catch (err: any) {
        if (err?.name !== 'RenderingCancelledException') {
          console.error('PDF rendering error:', err);
          setRenderError(err.message || 'Failed to render PDF page on canvas.');
        }
      }
    };

    renderPage();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {}
      }
    };
  }, [pdfDocProxy, currentPage, zoomLevel, fitToWidth, useNativeViewer]);

  if (!isOpen) return null;

  const isPdf =
    mimeType?.includes('pdf') ||
    activeTitle.toLowerCase().endsWith('.pdf') ||
    activeStreamUrl.toLowerCase().includes('.pdf');

  const isImage =
    mimeType?.includes('image') ||
    activeTitle.toLowerCase().endsWith('.png') ||
    activeTitle.toLowerCase().endsWith('.jpg') ||
    activeTitle.toLowerCase().endsWith('.jpeg');

  const handleZoomIn = () => {
    setFitToWidth(false);
    setZoomLevel((prev) => Math.min(prev + 20, 250));
  };

  const handleZoomOut = () => {
    setFitToWidth(false);
    setZoomLevel((prev) => Math.max(prev - 20, 50));
  };

  const handleResetZoom = () => {
    setFitToWidth(false);
    setZoomLevel(100);
  };

  const handleToggleFitToWidth = () => {
    setFitToWidth((prev) => !prev);
  };

  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage((p) => p - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage((p) => p + 1);
  };

  const handleJumpToPage = (pageNum: number) => {
    const valid = Math.min(Math.max(pageNum, 1), totalPages);
    setCurrentPage(valid);
  };

  // Find genuine bounding box for the current page
  const parsedBoundingBox = (() => {
    // 1. Check finding bounding box
    if (initialBoundingBox && activeTab === 'PRIMARY') {
      try {
        const b = typeof initialBoundingBox === 'string' ? JSON.parse(initialBoundingBox) : initialBoundingBox;
        if (b && typeof b.x === 'number') return b as BoundingBoxCoords;
      } catch {}
    }
    // 2. Check extracted fields for current page
    for (const ef of extractedFields) {
      if (ef.page_number === currentPage && ef.bounding_box) {
        try {
          const b = typeof ef.bounding_box === 'string' ? JSON.parse(ef.bounding_box) : ef.bounding_box;
          if (b && typeof b.x === 'number') return b as BoundingBoxCoords;
        } catch {}
      }
    }
    return null;
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-xs p-2 sm:p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 text-white rounded-2xl shadow-2xl w-full max-w-7xl h-[94vh] flex flex-col overflow-hidden border border-slate-700">
        {/* Top Header Bar */}
        <div className="px-5 py-3 bg-slate-950 border-b border-slate-800 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center space-x-3 min-w-0">
            <div className="p-2 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <FileText className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-sm text-white truncate max-w-md" title={activeTitle}>
                  {activeTitle}
                </h3>
                {categoryCode && activeTab === 'PRIMARY' && (
                  <span className="text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700 px-2 py-0.5 rounded uppercase">
                    {categoryCode.replace(/_/g, ' ')}
                  </span>
                )}
                {targetPage > 1 && (
                  <span className="text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded">
                    Evidence on Page {targetPage}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                <span>AICTE NIDHI Tamper-Evident Inspection Vault &bull; Official In-App Preview</span>
              </p>
            </div>
          </div>

          {/* Primary vs Comparison Document Tab Selector */}
          {secondaryDocumentId && (
            <div className="flex items-center bg-slate-800/90 p-1 rounded-xl border border-slate-700 shrink-0">
              <button
                type="button"
                onClick={() => {
                  setActiveTab('PRIMARY');
                  setCurrentPage(initialPage || 1);
                }}
                className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                  activeTab === 'PRIMARY'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Primary Attachment
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab('SECONDARY');
                  setCurrentPage(secondaryPageNumber || 1);
                }}
                className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 ${
                  activeTab === 'SECONDARY'
                    ? 'bg-amber-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Columns className="w-3.5 h-3.5" />
                <span>Comparison Document</span>
                {secondaryPageNumber && secondaryPageNumber > 1 && (
                  <span className="text-[10px] bg-slate-900/60 px-1.5 py-0.2 rounded font-mono">
                    P.{secondaryPageNumber}
                  </span>
                )}
              </button>
            </div>
          )}

          {/* Main Controls */}
          <div className="flex items-center space-x-2 shrink-0">
            {/* Page Navigation Controls */}
            {totalPages > 0 && !fetchError && (
              <div className="flex items-center bg-slate-800 border border-slate-700 rounded-lg p-0.5 text-xs text-slate-300">
                <button
                  type="button"
                  onClick={handlePrevPage}
                  disabled={currentPage <= 1 || loading}
                  className="p-1 hover:text-white disabled:opacity-30 disabled:hover:text-slate-300 transition-colors"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <div className="flex items-center px-1 font-mono text-[11px]">
                  <span>Page</span>
                  <input
                    type="number"
                    min={1}
                    max={totalPages}
                    value={currentPage}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      if (!isNaN(val)) handleJumpToPage(val);
                    }}
                    className="w-10 bg-slate-900 border border-slate-700 rounded text-center mx-1 py-0.5 text-white font-mono text-xs focus:outline-hidden focus:border-blue-500"
                  />
                  <span>of {totalPages}</span>
                </div>
                <button
                  type="button"
                  onClick={handleNextPage}
                  disabled={currentPage >= totalPages || loading}
                  className="p-1 hover:text-white disabled:opacity-30 disabled:hover:text-slate-300 transition-colors"
                  title="Next Page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Zoom Controls */}
            {!fetchError && (
              <div className="flex items-center bg-slate-800 border border-slate-700 rounded-lg p-0.5 text-xs text-slate-300">
                <button
                  type="button"
                  onClick={handleZoomOut}
                  disabled={loading}
                  className="p-1 hover:text-white disabled:opacity-30 transition-colors"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <span className="px-2 font-mono text-[11px]">{zoomLevel}%</span>
                <button
                  type="button"
                  onClick={handleZoomIn}
                  disabled={loading}
                  className="p-1 hover:text-white disabled:opacity-30 transition-colors"
                  title="Zoom In"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={handleToggleFitToWidth}
                  disabled={loading}
                  className={`p-1 hover:text-white border-l border-slate-700 ml-1 pl-1.5 transition-colors ${
                    fitToWidth ? 'text-blue-400 font-bold' : ''
                  }`}
                  title={fitToWidth ? 'Disable Fit to Width' : 'Fit to Width'}
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={handleResetZoom}
                  disabled={loading}
                  className="p-1 hover:text-white border-l border-slate-700 ml-1 pl-1.5 transition-colors"
                  title="Reset Zoom (100%)"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Native Browser PDF Viewer Toggle (fallback / preference) */}
            {isPdf && blobUrl && !fetchError && (
              <button
                type="button"
                onClick={() => setUseNativeViewer((prev) => !prev)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                  useNativeViewer
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
                }`}
                title={useNativeViewer ? 'Switch to Evidence Highlight Mode' : 'Switch to Native Browser Viewer'}
              >
                {useNativeViewer ? 'Highlights View' : 'Native View'}
              </button>
            )}

            {/* Toggle Extracted Data Drawer */}
            <button
              type="button"
              onClick={() => setShowMetadataPanel((prev) => !prev)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition-colors ${
                showMetadataPanel
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
              }`}
              title="Toggle Extracted Fields & Scrutiny Details"
            >
              <Layers className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Extracted Data</span>
              {extractedFields.length > 0 && (
                <span className="px-1.5 py-0.2 bg-blue-500 text-white rounded-full text-[10px] font-bold">
                  {extractedFields.length}
                </span>
              )}
            </button>

            {/* Open in External Tab / Download Fallback */}
            {blobUrl && (
              <a
                href={blobUrl}
                target="_blank"
                rel="noreferrer"
                download={activeTitle}
                className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                title="Open raw document stream in browser window or download"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-400 hover:text-white hover:bg-rose-600 transition-colors"
              title="Close Preview (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Main Viewport */}
        <div className="flex-1 flex overflow-hidden bg-slate-950/80 relative">
          {/* Main Document Display */}
          <div className="flex-1 flex flex-col items-center justify-center overflow-auto p-2 sm:p-4 bg-slate-950 relative">
            {/* Loading Spinner */}
            {loading && (
              <div className="flex flex-col items-center justify-center space-y-3 p-8">
                <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-sm font-semibold text-slate-300">
                  Retrieving secure stream from encrypted vault...
                </p>
                <p className="text-xs text-slate-500">
                  Verifying SHA-256 hash integrity & institutional access permissions
                </p>
              </div>
            )}

            {/* Clean Error State (NEVER raw API JSON inside viewer) */}
            {!loading && fetchError && (
              <div className="max-w-md w-full bg-slate-900 border border-rose-500/40 rounded-2xl p-6 text-center space-y-4 shadow-xl">
                <div className="w-12 h-12 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto">
                  <AlertTriangle className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-base font-bold text-white mb-1">{fetchError.title}</h4>
                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/70 p-3 rounded-lg border border-slate-800 font-mono">
                    {fetchError.detail}
                  </p>
                </div>
                <div className="text-[11px] text-slate-400">
                  AICTE regulatory security policy prevents unauthenticated or broken attachment requests from exposing raw server internals.
                </div>
                <div className="flex items-center justify-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={fetchDocumentBlob}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Retry Retrieval</span>
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-semibold border border-slate-700 transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            {/* PDF View (Canvas with Evidence Highlights OR Native Viewer) */}
            {!loading && !fetchError && isPdf && blobUrl && (
              <div className="w-full h-full flex items-center justify-center overflow-auto p-2">
                {useNativeViewer ? (
                  <iframe
                    key={`native-${activeStreamUrl}-${currentPage}`}
                    src={`${blobUrl}#page=${currentPage}&navpanes=1&toolbar=1`}
                    className="w-full h-full rounded-lg border border-slate-800 bg-white"
                    title={activeTitle}
                  />
                ) : (
                  <div className="relative inline-block shadow-2xl rounded-lg overflow-hidden border border-slate-800 bg-white">
                    <canvas ref={canvasRef} className="block max-w-full h-auto" />

                    {/* Genuine Bounding Box Overlay Highlight */}
                    {parsedBoundingBox && canvasRef.current && (
                      <div
                        className="absolute border-2 border-amber-400 bg-amber-400/25 rounded-xs transition-all pointer-events-none animate-pulse"
                        style={{
                          left: `${(parsedBoundingBox.x / parsedBoundingBox.page_width) * (canvasRef.current.clientWidth || 1)}px`,
                          top: `${(parsedBoundingBox.y / parsedBoundingBox.page_height) * (canvasRef.current.clientHeight || 1)}px`,
                          width: `${(parsedBoundingBox.width / parsedBoundingBox.page_width) * (canvasRef.current.clientWidth || 1)}px`,
                          height: `${(parsedBoundingBox.height / parsedBoundingBox.page_height) * (canvasRef.current.clientHeight || 1)}px`,
                          boxShadow: '0 0 16px rgba(245, 158, 11, 0.65)',
                        }}
                      >
                        <span className="absolute -top-5 left-0 text-[10px] font-bold bg-amber-500 text-slate-950 px-1 rounded shadow-xs whitespace-nowrap">
                          Evidence Highlight
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Image View (PNG / JPEG) */}
            {!loading && !fetchError && isImage && blobUrl && (
              <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
                <div
                  className="transition-transform duration-150 inline-block"
                  style={{
                    transform: `scale(${zoomLevel / 100})`,
                    transformOrigin: 'center center',
                  }}
                >
                  <img
                    src={blobUrl}
                    alt={activeTitle}
                    className="max-h-[82vh] max-w-full object-contain rounded-lg shadow-2xl border border-slate-800 bg-slate-900"
                  />
                </div>
              </div>
            )}

            {/* Other Formats Fallback */}
            {!loading && !fetchError && !isPdf && !isImage && blobUrl && (
              <div className="text-center p-8 max-w-md">
                <FileText className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <h4 className="font-bold text-slate-200 mb-2">{activeTitle}</h4>
                <p className="text-xs text-slate-400 mb-4">
                  This document format ({mimeType}) can be inspected directly via native browser stream or external viewer.
                </p>
                <a
                  href={blobUrl}
                  target="_blank"
                  rel="noreferrer"
                  download={activeTitle}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>Download / Open Document</span>
                </a>
              </div>
            )}
          </div>

          {/* Collapsible Extracted Data & Statutory Evidence Side Panel */}
          {showMetadataPanel && (
            <div className="w-80 sm:w-96 bg-slate-900 border-l border-slate-800 p-4 overflow-y-auto space-y-4 shrink-0 text-xs">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center space-x-1.5 text-slate-200 font-bold">
                  <ShieldCheck className="w-4 h-4 text-blue-400" />
                  <span>Document Intelligence</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowMetadataPanel(false)}
                  className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Active Tab Notice */}
              {secondaryDocumentId && (
                <div className="p-2.5 bg-slate-800/80 rounded-lg border border-slate-700/80 flex items-center justify-between">
                  <span className="text-[11px] text-slate-300 font-medium">Viewing Document:</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    activeTab === 'PRIMARY' ? 'bg-blue-600 text-white' : 'bg-amber-600 text-white'
                  }`}>
                    {activeTab === 'PRIMARY' ? 'Primary Document' : 'Comparison Document'}
                  </span>
                </div>
              )}

              {/* Verification Status Pill */}
              {verificationStatus && activeTab === 'PRIMARY' && (
                <div className="p-3 bg-slate-800/80 rounded-xl border border-slate-700/80 space-y-1">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block">
                    Verification Outcome
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                        verificationStatus === 'VERIFIED'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : verificationStatus === 'EXPIRED'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      }`}
                    >
                      {verificationStatus}
                    </span>
                    {verificationSource && (
                      <span className="text-[10px] text-slate-300 truncate" title={verificationSource}>
                        via {verificationSource}
                      </span>
                    )}
                  </div>
                  {verificationEvidence && (
                    <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                      {verificationEvidence}
                    </p>
                  )}
                </div>
              )}

              {/* Referenced Finding Evidence Snippet */}
              {supportingSnippet && (
                <div className="p-3 bg-blue-950/40 rounded-xl border border-blue-800/60 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase text-blue-400 block">
                      Referenced Finding Evidence
                    </span>
                    {initialPage && (
                      <span className="text-[10px] font-bold bg-blue-900/60 text-blue-200 px-1.5 py-0.2 rounded border border-blue-700/50">
                        Page {initialPage}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-blue-200 font-mono bg-blue-900/30 p-2.5 rounded border border-blue-800/40 whitespace-pre-wrap leading-relaxed select-text">
                    {supportingSnippet}
                  </p>
                </div>
              )}

              {/* Extracted Structured OCR / IDP Fields (Real values from backend only) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-400">
                    Extracted Regulatory Fields
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {loadingDetails ? 'Loading...' : `${extractedFields.length} fields`}
                  </span>
                </div>

                {extractedFields.length > 0 ? (
                  <div className="space-y-2">
                    {extractedFields.map((field) => (
                      <div
                        key={field.id}
                        onClick={() => handleJumpToPage(field.page_number)}
                        className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                          currentPage === field.page_number
                            ? 'bg-blue-950/50 border-blue-600/70 ring-1 ring-blue-500/30'
                            : 'bg-slate-800/60 border-slate-700/70 hover:bg-slate-800'
                        }`}
                        title={`Click to jump to Page ${field.page_number}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-slate-200 text-xs">
                            {field.field_key.replace(/_/g, ' ').toUpperCase()}
                          </span>
                          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-slate-900 text-blue-300 border border-slate-700">
                            Page {field.page_number}
                          </span>
                        </div>
                        <div className="text-sm font-bold text-white font-mono break-all">
                          {field.field_value}
                        </div>
                        {field.source_snippet && field.source_snippet !== field.field_value && (
                          <div className="text-[11px] text-slate-400 mt-1 font-mono line-clamp-2">
                            "{field.source_snippet}"
                          </div>
                        )}
                        <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-700/50 text-[10px] text-slate-400">
                          <span>Confidence: {Math.round(field.confidence_score * 100)}%</span>
                          <span className="uppercase text-[9px] text-slate-500 font-semibold">
                            {field.extraction_method || 'PARSER'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50 text-center text-slate-400 text-xs">
                    {loadingDetails ? 'Extracting document fields...' : 'No structured regulatory fields extracted for this attachment.'}
                  </div>
                )}
              </div>

              {/* Raw Extracted Text Drawer / Snippet */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-400">
                    Full Extracted Text
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {extractedTextContent ? `${extractedTextContent.length} chars` : '0 chars'}
                  </span>
                </div>
                {extractedTextContent ? (
                  <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 max-h-48 overflow-y-auto text-[11px] text-slate-300 font-mono leading-relaxed whitespace-pre-wrap select-text">
                    {extractedTextContent}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50 text-center text-slate-400 text-xs">
                    No OCR or machine-readable text was extracted from this attachment.
                  </div>
                )}
              </div>

              {/* AICTE Handbook Guidance Note */}
              <div className="p-3 bg-slate-800/50 rounded-xl border border-slate-700 text-[11px] text-slate-400 flex items-start gap-2">
                <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                <p>
                  AICTE Scrutiny Officers inspect the raw statutory certificate to verify official stamps, signatures, and issuing authority validity dates.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Bottom Status Bar */}
        <div className="px-5 py-2.5 bg-slate-950 border-t border-slate-800 flex flex-wrap items-center justify-between text-xs text-slate-400 shrink-0">
          <div className="flex items-center space-x-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
            <span>Tamper-Evident Storage &bull; Streamed securely from AICTE Encrypted Vault</span>
          </div>
          <div className="flex items-center space-x-3">
            <span>Press <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-[10px] font-mono text-slate-300">Esc</kbd> to close</span>
          </div>
        </div>
      </div>
    </div>
  );
};
