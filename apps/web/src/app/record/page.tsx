"use client";

import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Mic, Square, Check, ArrowLeft, Loader2, Type, Upload } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { ingestMemoryEvent } from "@/lib/memoryClient";
import type { MemoryEvent, MemoryWarning } from "@/lib/memoryClient";
import { SafetyBanner } from "@/components/SafetyBanner";
import { MobileNav } from "@/components/mobile-nav";

type Step =
  | "idle"
  | "recording"
  | "transcribing"
  | "confirm"
  | "saving"
  | "done"
  | "error";

type InputMode = "voice" | "text" | "upload";

const PATIENT_ID = "p_001";

type SpeechRecognitionAlternativeLike = {
  transcript: string;
};

type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0: SpeechRecognitionAlternativeLike;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
};

type SpeechRecognitionErrorEventLike = {
  error: string;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type WindowWithSpeechRecognition = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

async function extractMemoryFromTranscript(
  transcript: string
): Promise<Partial<MemoryEvent>> {
  const response = await fetch(`${API_BASE_URL}/api/stt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`STT extract failed with status ${response.status}`);
  }

  const data = (await response.json()) as {
    transcript?: string;
    event_type?: MemoryEvent["event_type"];
    entities?: MemoryEvent["entities"];
  };

  return {
    transcript: data.transcript ?? transcript,
    event_type: data.event_type ?? "general",
    entities: data.entities,
  };
}

export default function RecordMemoryPage() {
  const router = useRouter();
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const speechRecognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = useRef("");
  const speechErrorRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [inputMode, setInputMode] = useState<InputMode>("voice");
  const [textInput, setTextInput] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [transcript, setTranscript] = useState("");
  const [pendingEvent, setPendingEvent] = useState<Partial<MemoryEvent> | null>(null);
  const [warning, setWarning] = useState<MemoryWarning | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Theme classes
  const bg = "bg-gradient-to-br from-rose-50 via-orange-50 to-amber-50";
  const headingCls = "text-stone-800";
  const subtextCls = "text-stone-500";
  const backCls = "text-stone-500 hover:text-stone-700";
  const cardCls = "bg-white border-stone-100";
  const cardLabelCls = "text-stone-400";
  const cardBodyCls = "text-stone-800";
  const retryBtnCls = "bg-stone-100 text-stone-700 hover:bg-stone-200";
  const tabActiveCls = "bg-rose-400 text-white";
  const tabInactiveCls = "bg-white text-stone-500 hover:bg-stone-50";
  const tabBorderCls = "border-stone-200 divide-stone-200";
  const textareaCls = "border-stone-200 bg-white text-stone-800 placeholder-stone-300";
  const uploadBorderCls = "border-stone-300 text-stone-500 hover:border-rose-400";

  const stopSpeechRecognition = useCallback(async (): Promise<void> => {
    const recognition = speechRecognitionRef.current;
    if (!recognition) return;

    await new Promise<void>((resolve) => {
      let settled = false;

      const finish = () => {
        if (settled) return;
        settled = true;
        resolve();
      };

      const timeout = window.setTimeout(finish, 800);

      recognition.onend = () => {
        window.clearTimeout(timeout);
        finish();
      };

      try {
        recognition.stop();
      } catch {
        window.clearTimeout(timeout);
        finish();
      }
    });

    speechRecognitionRef.current = null;
  }, []);

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrorMsg(
        "Audio recording is not supported in this browser. Please use Chrome or Edge."
      );
      setStep("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const speechWindow = window as WindowWithSpeechRecognition;
      const SpeechRecognitionCtor =
        speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;

      if (!SpeechRecognitionCtor) {
        stream.getTracks().forEach((t) => t.stop());
        setErrorMsg(
          "Live speech transcription is not supported in this browser. Please use Chrome or Edge."
        );
        setStep("error");
        return;
      }

      transcriptRef.current = "";
      speechErrorRef.current = null;

      const recognition = new SpeechRecognitionCtor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.maxAlternatives = 1;

      recognition.onresult = (event) => {
        let finalChunk = "";

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          if (result?.isFinal && result[0]?.transcript) {
            finalChunk += ` ${result[0].transcript}`;
          }
        }

        if (finalChunk.trim()) {
          transcriptRef.current = `${transcriptRef.current} ${finalChunk}`.trim();
        }
      };

      recognition.onerror = (event) => {
        const code = event.error;
        if (code === "not-allowed") {
          speechErrorRef.current =
            "Microphone access was blocked. Please allow microphone access and try again.";
          return;
        }
        if (code === "no-speech") {
          speechErrorRef.current =
            "I could not hear speech clearly. Please speak a bit louder and try again.";
          return;
        }
        speechErrorRef.current = `Speech recognition failed (${code}). Please try again.`;
      };

      speechRecognitionRef.current = recognition;

      const mr = new MediaRecorder(stream);

      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setStep("transcribing");

        try {
          await stopSpeechRecognition();

          if (speechErrorRef.current) {
            throw new Error(speechErrorRef.current);
          }

          const spokenTranscript = transcriptRef.current.trim();
          if (!spokenTranscript) {
            throw new Error(
              "No speech was captured. Please hold the phone closer and try again."
            );
          }

          let partial: Partial<MemoryEvent>;
          try {
            partial = await extractMemoryFromTranscript(spokenTranscript);
          } catch {
            partial = {
              transcript: spokenTranscript,
              event_type: "general",
            };
          }

          setPendingEvent(partial);
          setTranscript(partial.transcript ?? spokenTranscript);
          setStep("confirm");
        } catch (err) {
          console.error("Transcription error:", err);
          setErrorMsg(
            err instanceof Error
              ? err.message
              : "Could not process your recording. Please try again."
          );
          setStep("error");
        }
      };

      try {
        recognition.start();
        mr.start();
        mediaRecorderRef.current = mr;
        setStep("recording");
      } catch (err) {
        stream.getTracks().forEach((t) => t.stop());
        await stopSpeechRecognition();
        throw err;
      }
    } catch (err) {
      console.error("Mic error:", err);
      const name = err instanceof Error ? (err as DOMException).name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setErrorMsg(
          "Microphone access was blocked.\n\nTo fix: click the 🔒 lock icon in your browser address bar → set Microphone to Allow → refresh this page."
        );
      } else if (name === "NotFoundError") {
        setErrorMsg(
          "No microphone found. Please connect a microphone and try again."
        );
      } else {
        const detail = err instanceof Error ? err.message : String(err);
        setErrorMsg(`Microphone problem: ${detail}`);
      }
      setStep("error");
    }
  }, [stopSpeechRecognition]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  const submitTextMemory = useCallback(async () => {
    if (!textInput.trim()) return;
    setStep("transcribing");
    try {
      let partial: Partial<MemoryEvent>;
      try {
        partial = await extractMemoryFromTranscript(textInput.trim());
      } catch {
        partial = {
          transcript: textInput.trim(),
          event_type: "general",
        };
      }
      setPendingEvent(partial);
      setTranscript(partial.transcript ?? textInput.trim());
      setStep("confirm");
    } catch (err) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Could not process your text. Please try again."
      );
      setStep("error");
    }
  }, [textInput]);

  const submitFileMemory = useCallback(() => {
    if (!uploadedFile) return;
    const fileDescription = `Uploaded file: ${uploadedFile.name}`;
    const partial: Partial<MemoryEvent> = {
      transcript: fileDescription,
      event_type: "general",
    };
    setPendingEvent(partial);
    setTranscript(fileDescription);
    setStep("confirm");
  }, [uploadedFile]);

  const saveMemory = useCallback(async () => {
    if (!pendingEvent) return;
    setStep("saving");
    try {
      const source =
        inputMode === "upload"
          ? "document"
          : inputMode === "text"
          ? "manual"
          : "voice_note";
      const event: MemoryEvent = {
        patient_id: PATIENT_ID,
        source,
        recorded_at: new Date().toISOString(),
        event_type: pendingEvent.event_type ?? "general",
        transcript: pendingEvent.transcript ?? null,
        entities: pendingEvent.entities,
      };
      const result = await ingestMemoryEvent(event);
      setWarning(result.warning ?? null);
      setStep("done");
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      const origin = typeof window !== "undefined" ? window.location.origin : "";

      if (detail.toLowerCase().includes("unreachable")) {
        setErrorMsg(
          `Could not reach the Memory API from ${origin}.\n\n` +
            "If you opened the app on 127.0.0.1 or a LAN IP, add that origin to API CORS settings (CORS_ORIGINS) and try again."
        );
      } else {
        setErrorMsg(detail || "Could not save. Please try again.");
      }
      setStep("error");
    }
  }, [pendingEvent, inputMode]);

  const reset = useCallback(() => {
    setStep("idle");
    setTranscript("");
    setPendingEvent(null);
    setWarning(null);
    setErrorMsg("");
    setTextInput("");
    setUploadedFile(null);
    transcriptRef.current = "";
    speechErrorRef.current = null;
  }, []);

  return (
    <main className={`min-h-screen ${bg}`}>
      <div className="app-shell app-shell--nav flex min-h-screen flex-col gap-4">
      <button
        type="button"
        onClick={() => router.back()}
        className={`flex items-center gap-1.5 ${backCls} text-sm self-start`}
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back
      </button>

      <h1 className={`text-3xl font-semibold ${headingCls}`}>Record a Memory</h1>

      {/* ── Idle ─────────────────────────────────────────────────────── */}
      {step === "idle" && (
        <div className="flex flex-col gap-4">
          {/* Mode selector */}
          <div className={`app-card flex overflow-hidden ${tabBorderCls} divide-x`}>
            {(["voice", "text", "upload"] as InputMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setInputMode(mode)}
                className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${
                  inputMode === mode ? tabActiveCls : tabInactiveCls
                }`}
              >
                {mode === "voice" && "🎙 Voice"}
                {mode === "text" && "✏️ Type"}
                {mode === "upload" && "📎 Upload"}
              </button>
            ))}
          </div>

          {/* Voice mode */}
          {inputMode === "voice" && (
            <div className="flex flex-col items-center gap-5 pt-2">
              <p className={`text-sm ${subtextCls} text-center`}>
                Tap the button and speak
              </p>
              <button
                type="button"
                onClick={startRecording}
                className="h-28 w-28 rounded-full bg-teal-600 flex items-center justify-center shadow-xl active:scale-95 transition-transform"
                aria-label="Start recording"
              >
                <Mic className="h-14 w-14 text-white" aria-hidden="true" />
              </button>
            </div>
          )}

          {/* Text mode */}
          {inputMode === "text" && (
            <div className="flex flex-col gap-3 pt-1">
              <p className={`text-sm ${subtextCls}`}>Type your memory</p>
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Write what you'd like to remember..."
                rows={5}
                className={`w-full rounded-xl border ${textareaCls} p-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none`}
              />
              <button
                type="button"
                onClick={submitTextMemory}
                disabled={!textInput.trim()}
                className="app-button w-full rounded-xl bg-teal-600 px-4 py-3 text-sm text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Type className="h-4 w-4" aria-hidden="true" />
                Save text memory
              </button>
            </div>
          )}

          {/* Upload mode */}
          {inputMode === "upload" && (
            <div className="flex flex-col gap-3 pt-1">
              <p className={`text-sm ${subtextCls}`}>Upload a file</p>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.pdf"
                className="hidden"
                onChange={(e) => setUploadedFile(e.target.files?.[0] ?? null)}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className={`w-full rounded-xl border-2 border-dashed ${uploadBorderCls} px-4 py-8 text-sm flex flex-col items-center gap-2 transition-colors`}
              >
                <Upload className="h-8 w-8" aria-hidden="true" />
                {uploadedFile ? (
                  <span className="font-medium break-all">{uploadedFile.name}</span>
                ) : (
                  <span>Tap to choose a photo or PDF</span>
                )}
              </button>
              {uploadedFile && (
                <button
                  type="button"
                  onClick={submitFileMemory}
                  className="app-button w-full rounded-xl bg-teal-600 px-4 py-3 text-sm text-white shadow-sm flex items-center justify-center gap-2"
                >
                  <Check className="h-4 w-4" aria-hidden="true" />
                  Save this file
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Recording ────────────────────────────────────────────────── */}
      {step === "recording" && (
        <div className="flex flex-col items-center gap-5 pt-4">
          <p className="text-sm text-teal-700 text-center animate-pulse font-medium">
            Listening... speak now
          </p>
          <button
            type="button"
            onClick={stopRecording}
            className="h-28 w-28 rounded-full bg-slate-900 flex items-center justify-center shadow-xl active:scale-95 transition-transform"
            aria-label="Stop recording"
          >
            <Square className="h-14 w-14 text-white" aria-hidden="true" />
          </button>
          <p className={`text-sm ${subtextCls}`}>Tap to stop</p>
        </div>
      )}

      {/* ── Transcribing ─────────────────────────────────────────────── */}
      {step === "transcribing" && (
        <div className="flex flex-col items-center gap-3 pt-10">
          <Loader2
            className="h-10 w-10 text-teal-500 animate-spin"
            aria-hidden="true"
          />
          <p className={`text-sm ${subtextCls}`}>Processing your words…</p>
        </div>
      )}

      {/* ── Confirm ──────────────────────────────────────────────────── */}
      {step === "confirm" && (
        <div className="flex flex-col gap-3">
          <div className={`app-card ${cardCls} p-4`}>
            <p className={`text-xs ${cardLabelCls} mb-1.5`}>
              {inputMode === "upload" ? "File selected:" : inputMode === "text" ? "You wrote:" : "I heard:"}
            </p>
            <p className={`text-sm font-medium ${cardBodyCls} leading-relaxed`}>
              {transcript}
            </p>
          </div>
          <button
            type="button"
            onClick={saveMemory}
            className="app-button w-full rounded-xl bg-emerald-600 px-4 py-3 text-sm text-white shadow-sm flex items-center justify-center gap-2"
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            Save this memory
          </button>
          <button
            type="button"
            onClick={reset}
            className={`app-button w-full rounded-xl ${retryBtnCls} px-4 py-2.5 text-sm active:scale-95 transition-transform`}
          >
            Try again
          </button>
        </div>
      )}

      {/* ── Saving ───────────────────────────────────────────────────── */}
      {step === "saving" && (
        <div className="flex flex-col items-center gap-3 pt-10">
          <Loader2
            className="h-10 w-10 text-emerald-600 animate-spin"
            aria-hidden="true"
          />
          <p className={`text-sm ${subtextCls}`}>Saving your memory…</p>
        </div>
      )}

      {/* ── Done ─────────────────────────────────────────────────────── */}
      {step === "done" && (
        <div className="flex flex-col gap-3">
          <div className="app-card border-emerald-300 bg-emerald-50 p-5 text-center">
            <p className="text-3xl mb-2" aria-hidden="true">✅</p>
            <p className="text-lg font-semibold text-emerald-900">Memory saved!</p>
            <p className="mt-1 text-sm text-emerald-700">
              Your memory is safely stored.
            </p>
          </div>

          {warning && <SafetyBanner warning={warning} />}

          <button
            type="button"
            onClick={reset}
            className="app-button w-full rounded-xl bg-teal-600 px-4 py-3 text-sm text-white shadow-sm flex items-center justify-center gap-2"
          >
            <Mic className="h-4 w-4" aria-hidden="true" />
            Record another
          </button>
          <button
            type="button"
            onClick={() => router.push("/")}
            className={`app-button w-full rounded-xl ${retryBtnCls} px-4 py-2.5 text-sm active:scale-95 transition-transform`}
          >
            Go home
          </button>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────────── */}
      {step === "error" && (
        <div className="flex flex-col gap-3">
          <div className="app-card border-rose-300 bg-rose-50 p-5 text-center">
            <p className="text-3xl mb-2" aria-hidden="true">😕</p>
            <p className="text-lg font-semibold text-rose-900">
              Something went wrong
            </p>
            <p className="mt-1 text-sm text-rose-700 whitespace-pre-line">{errorMsg}</p>
          </div>
          <button
            type="button"
            onClick={reset}
            className="app-button w-full rounded-xl bg-teal-600 px-4 py-3 text-sm text-white shadow-sm"
          >
            Try again
          </button>
        </div>
      )}
      </div>
      <MobileNav />
    </main>
  );
}
