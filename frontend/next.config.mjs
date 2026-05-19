/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverComponentsExternalPackages: ["html2canvas", "jspdf"],
  },
};

export default nextConfig;
