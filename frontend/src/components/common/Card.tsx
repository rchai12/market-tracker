interface CardProps {
  children: React.ReactNode;
  padding?: "none" | "sm" | "md";
  className?: string;
}

export default function Card({ children, padding = "sm", className = "" }: CardProps) {
  const pad = padding === "md" ? "p-6" : padding === "none" ? "" : "p-4";
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl shadow ${pad} ${className}`}>
      {children}
    </div>
  );
}
