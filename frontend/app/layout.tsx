import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Providers } from "@/components/providers";

const dmSans = DM_Sans({ subsets: ["latin"], weight: ["300", "400", "500", "600"] });

export const metadata: Metadata = {
  title: "ReCiter Desktop",
  description: "Author name disambiguation for your institution",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${dmSans.className} bg-[#f5f2ee] text-gray-900`}>
        <header className="bg-[#1a2133] text-white px-0 flex items-center justify-between h-[52px] sticky top-0 z-50 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5 w-[220px] px-5 h-full border-r border-white/[0.07]">
            <span className="w-2 h-2 rounded-full bg-[#e05a5a] shrink-0" />
            <span className="font-semibold text-[13.5px] tracking-wide">ReCiter Desktop</span>
          </div>
        </header>
        <Providers>
          <div className="flex min-h-[calc(100vh-52px)]">
            <Sidebar />
            <main className="flex-1 p-8 bg-[#f5f2ee]">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
