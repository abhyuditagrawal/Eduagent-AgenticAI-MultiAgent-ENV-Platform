"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Mic, MicOff, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";

interface VoiceModeProps {
  onTranscript: (text: string) => void;
  textToSpeak?: string;
  isActive: boolean;
}

export function VoiceMode({ onTranscript, textToSpeak, isActive }: VoiceModeProps) {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [supported, setSupported] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const w = window as any;
    const SpeechRecognition = w.SpeechRecognition || w.webkitSpeechRecognition;

    if (SpeechRecognition) {
      setSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onresult = (event: { results: { 0: { 0: { transcript: string } } } }) => {
        const transcript = event.results[0][0].transcript;
        onTranscript(transcript);
        setIsListening(false);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }

    return () => {
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, [onTranscript]);

  // Text-to-speech when new response arrives
  useEffect(() => {
    if (textToSpeak && ttsEnabled && isActive && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(textToSpeak);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
    }
  }, [textToSpeak, ttsEnabled, isActive]);

  const toggleListening = useCallback(() => {
    if (!recognitionRef.current) return;

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      recognitionRef.current.start();
      setIsListening(true);
    }
  }, [isListening]);

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel();
    setIsSpeaking(false);
  };

  if (!supported || !isActive) return null;

  return (
    <div className="flex items-center gap-1">
      <Button
        variant={isListening ? "destructive" : "outline"}
        size="icon"
        className="h-8 w-8"
        onClick={toggleListening}
        title={isListening ? "Stop listening" : "Start voice input"}
      >
        {isListening ? (
          <MicOff className="h-4 w-4 animate-pulse" />
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={() => {
          if (isSpeaking) {
            stopSpeaking();
          } else {
            setTtsEnabled(!ttsEnabled);
          }
        }}
        title={ttsEnabled ? "Disable text-to-speech" : "Enable text-to-speech"}
      >
        {ttsEnabled ? (
          <Volume2 className={`h-4 w-4 ${isSpeaking ? "text-primary animate-pulse" : ""}`} />
        ) : (
          <VolumeX className="h-4 w-4 text-muted-foreground" />
        )}
      </Button>

      {isListening && (
        <span className="text-xs text-red-500 animate-pulse">Listening...</span>
      )}
    </div>
  );
}
