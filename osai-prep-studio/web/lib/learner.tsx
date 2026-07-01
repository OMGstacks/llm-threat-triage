"use client";

import { createContext, useContext, useEffect, useState } from "react";

interface LearnerCtx {
  learner: string;
  setLearner: (v: string) => void;
}

const Ctx = createContext<LearnerCtx>({ learner: "demo", setLearner: () => {} });

export function LearnerProvider({ children }: { children: React.ReactNode }) {
  const [learner, setState] = useState("demo");

  useEffect(() => {
    const saved =
      typeof window !== "undefined" ? window.localStorage.getItem("osai_learner") : null;
    if (saved) setState(saved);
  }, []);

  const setLearner = (v: string) => {
    setState(v);
    if (typeof window !== "undefined") window.localStorage.setItem("osai_learner", v);
  };

  return <Ctx.Provider value={{ learner, setLearner }}>{children}</Ctx.Provider>;
}

export function useLearner(): LearnerCtx {
  return useContext(Ctx);
}
