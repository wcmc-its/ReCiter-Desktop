import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Providers } from "@/components/providers";

const inter = Inter({ subsets: ["latin"] });

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
      <body className={`${inter.className} bg-[#f0f2f5] text-gray-900`}>
        <header className="bg-[#2d3b45] text-white px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#cf4520]" />
            <span className="font-semibold text-sm tracking-wide">ReCiter Desktop</span>
          </div>
        </header>
        <Providers>
          <div className="flex min-h-[calc(100vh-48px)]">
            <Sidebar />
            <main className="flex-1 p-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
