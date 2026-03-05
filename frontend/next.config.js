/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' }
    ]
  },
  experimental: {
    serverComponentsExternalPackages: ['@libsql/client']
  },
}

module.exports = nextConfig
