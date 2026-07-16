import { GraduationCap } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center space-y-2">
          <div className="flex items-center gap-2 text-primary">
            <GraduationCap className="h-10 w-10" />
            <h1 className="text-3xl font-bold tracking-tight">EduAgent</h1>
          </div>
          <p className="text-muted-foreground text-sm">
            Multi-Agent AI Educational Platform
          </p>
        </div>
        {children}
      </div>
    </div>
  );
}
