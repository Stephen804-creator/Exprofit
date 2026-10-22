import { useEffect, useRef, useState } from "react";

type FaceCaptureProps = {
  onCapture: (photoDataUrl: string) => void;
  onError: (message: string) => void;
};
type FaceBox = { originX: number; originY: number; width: number; height: number };
type FaceDetectionResult = { detections?: Array<{ boundingBox?: FaceBox }> };
type FaceDetectorInstance = {
  detectForVideo: (video: HTMLVideoElement, timestamp: number) => FaceDetectionResult;
  close: () => void;
};
type VisionModule = {
  FilesetResolver: { forVisionTasks: (path: string) => Promise<unknown> };
  FaceDetector: {
    createFromOptions: (files: unknown, options: Record<string, unknown>) => Promise<FaceDetectorInstance>;
  };
};

const VISION_MODULE_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/+esm";
const WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm";
const FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite";
const MAX_PHOTO_BYTES = 15 * 1024 * 1024;

function cameraErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Camera permission is blocked by your browser or device. Open the browser's site settings for exprofit.onrender.com, set Camera to Allow, return here, and tap Try camera again. On Android, open this page directly in Chrome instead of an in-app browser.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "No camera was found on this device. Connect or enable a camera, then try again.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "The camera is already being used by another app or is unavailable. Close other camera apps and try again.";
  }
  if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
    return "This device could not start the requested camera mode. Try again or use another camera-enabled browser.";
  }
  if (name === "SecurityError" || !window.isSecureContext) {
    return "Camera access requires a secure HTTPS page. Open Exprofit using its https:// address.";
  }
  if (error instanceof Error && /fetch|network|import|wasm|model/i.test(error.message)) {
    return "The camera opened, but face-detection files could not load. Check your internet connection, then tap Try camera again.";
  }
  return "The camera could not be started. Check browser permissions and device settings, then tap Try camera again.";
}

export default function FaceCapture({ onCapture, onError }: FaceCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const detectorRef = useRef<FaceDetectorInstance | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRef = useRef<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [cameraReady, setCameraReady] = useState(false);
  const [faceReady, setFaceReady] = useState(false);
  const [status, setStatus] = useState("Requesting camera access…");
  const [capturing, setCapturing] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let detector: FaceDetectorInstance | null = null;
    const stopCamera = () => {
      if (frameRef.current !== null) window.clearTimeout(frameRef.current);
      frameRef.current = null;
      detector?.close();
      detector = null;
      detectorRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };

    async function start(): Promise<void> {
      setLoading(true);
      setCameraReady(false);
      setFaceReady(false);
      setCameraError("");
      setStatus("Requesting camera access…");
      try {
        if (!window.isSecureContext) {
          throw new DOMException("Camera access requires HTTPS.", "SecurityError");
        }
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new DOMException("Camera API unavailable.", "SecurityError");
        }
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: "user" }, width: { ideal: 1280 }, height: { ideal: 1280 } },
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (!video) throw new Error("Camera preview could not be started.");
        video.srcObject = stream;
        await video.play();
        if (cancelled) return;
        setCameraReady(true);
        setStatus("Camera opened. Loading face detection…");

        const dynamicImport = new Function("url", "return import(url)") as (url: string) => Promise<VisionModule>;
        const vision = await dynamicImport(VISION_MODULE_URL);
        const files = await vision.FilesetResolver.forVisionTasks(WASM_URL);
        detector = await vision.FaceDetector.createFromOptions(files, {
          baseOptions: { modelAssetPath: FACE_MODEL_URL, delegate: "CPU" },
          runningMode: "VIDEO",
          minDetectionConfidence: 0.65,
        });
        if (cancelled) {
          detector.close();
          detector = null;
          return;
        }
        detectorRef.current = detector;
        setLoading(false);

        const scan = () => {
          const currentVideo = videoRef.current;
          const currentDetector = detectorRef.current;
          if (cancelled) return;
          if (!currentVideo || currentVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !currentDetector) {
            frameRef.current = window.setTimeout(scan, 160);
            return;
          }
          try {
            const result = currentDetector.detectForVideo(currentVideo, performance.now());
            const box = result.detections?.[0]?.boundingBox;
            if (!box || currentVideo.videoWidth === 0 || currentVideo.videoHeight === 0) {
              setFaceReady(false);
              setStatus("No face detected. Face the camera and move into the oval.");
            } else {
              const centerX = (box.originX + box.width / 2) / currentVideo.videoWidth;
              const centerY = (box.originY + box.height / 2) / currentVideo.videoHeight;
              const widthRatio = box.width / currentVideo.videoWidth;
              const heightRatio = box.height / currentVideo.videoHeight;
              const centered = centerX >= 0.28 && centerX <= 0.72 &&
                centerY >= 0.22 && centerY <= 0.76 &&
                widthRatio >= 0.12 && widthRatio <= 0.72 &&
                heightRatio >= 0.12 && heightRatio <= 0.82;
              setFaceReady(centered);
              setStatus(centered
                ? "Face detected. Hold still and capture."
                : "Face found, but not positioned in the oval. Move closer or center your face.");
            }
          } catch {
            setFaceReady(false);
            setStatus("Could not analyze this camera frame. Keep the camera open and try again.");
          }
          frameRef.current = window.setTimeout(scan, 160);
        };
        frameRef.current = window.setTimeout(scan, 160);
      } catch (error) {
        if (!cancelled) {
          stopCamera();
          const message = cameraErrorMessage(error);
          setCameraError(message);
          setStatus(message);
          setLoading(false);
          onError(message);
        }
      }
    }
    void start();
    return () => {
      cancelled = true;
      stopCamera();
    };
  }, [attempt, onError]);

  async function captureFace(): Promise<void> {
    const video = videoRef.current;
    if (!video || !faceReady || capturing) return;
    setCapturing(true);
    try {
      const canvas = document.createElement("canvas");
      const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Could not prepare the captured photo.");
      context.translate(canvas.width, 0);
      context.scale(-1, 1);
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      let quality = 0.9;
      let blob: Blob | null = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      while (blob && blob.size > MAX_PHOTO_BYTES && quality > 0.45) {
        quality -= 0.1;
        blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      }
      if (!blob) throw new Error("The photo could not be encoded. Please try again.");
      if (blob.size > MAX_PHOTO_BYTES) throw new Error("The captured photo is still too large. Move into better light and try again.");
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          onCapture(reader.result);
          setStatus("Face detected and photo captured. You can retake it if needed.");
        } else {
          onError("The captured photo could not be read.");
        }
        setCapturing(false);
      };
      reader.onerror = () => {
        onError("The captured photo could not be read.");
        setCapturing(false);
      };
      reader.readAsDataURL(blob);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not capture the photo.");
      setCapturing(false);
    }
  }

  return (
    <section className="face-capture" aria-label="Face capture">
      <p className="form-hint">Center your face inside the oval. Exprofit checks that a face is visible before enabling capture. This detects a face; it does not identify who the person is or prove liveness.</p>
      <div className={"face-camera-frame " + (faceReady ? "face-camera-frame--ready" : "")}>
        <video ref={videoRef} className="face-camera-video" autoPlay muted playsInline aria-label="Front camera preview" />
        <div className="face-guide-oval" aria-hidden="true" />
        {(!cameraReady || loading) && <div className="face-camera-loading">{status}</div>}
      </div>
      <p className={"face-capture-status " + (faceReady ? "face-capture-status--ready" : "")} role="status">{status}</p>
      {cameraError && <div className="camera-permission-help" role="alert">
        <strong>Camera or face detection needs attention</strong>
        <p>{cameraError}</p>
        <ol>
          <li>Open the browser menu and find Site settings or Permissions.</li>
          <li>Set Camera to Allow for exprofit.onrender.com.</li>
          <li>Return to this page and tap Try camera again. If the browser previously blocked it, reload the page after changing settings.</li>
        </ol>
        <button className="button button--primary" type="button" onClick={() => setAttempt((value) => value + 1)}>Try camera again</button>
      </div>}
      <div className="face-capture-actions">
        <button className="button button--primary" type="button" onClick={() => void captureFace()} disabled={!faceReady || loading || capturing}>
          {capturing ? "Capturing…" : "Capture face photo"}
        </button>
        <span className="form-hint">Camera images stay in this browser until you submit the application.</span>
      </div>
    </section>
  );
}
