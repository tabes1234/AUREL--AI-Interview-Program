/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 观澜设计令牌：海天蓝白体系
        surface: '#F8FBFF', // 主背景
        mist: '#F0F7FF', // 浅蓝（次要数据区）
        shallow: '#DCEBFF', // 淡蓝（强调底色）
        ripple: '#BDD8FC', // 云水蓝（装饰/描边强调）
        brand: {
          DEFAULT: '#4D83D6', // 主蓝
          50: '#F0F7FF',
          100: '#DCEBFF',
          200: '#BDD8FC',
          300: '#9CC0F2',
          600: '#4D83D6',
          700: '#315FAD', // 深蓝
        },
        accent: {
          DEFAULT: '#0F766E',
          50: '#F0FDFA',
          100: '#CCFBF1',
          700: '#115E59',
        },
        ink: {
          DEFAULT: '#263B57', // 正文
          strong: '#1C2F4A', // 标题
          soft: '#7185A2', // 辅助文字
        },
        line: '#DCE8F7', // 边框
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px rgba(49, 95, 173, 0.05), 0 2px 6px rgba(49, 95, 173, 0.06)',
        raised: '0 12px 32px rgba(28, 47, 74, 0.10)',
        hero: '0 20px 60px rgba(28, 47, 74, 0.14)',
      },
      backgroundImage: {
        'sidebar-wash': 'linear-gradient(180deg, #EFF6FF 0%, #F8FBFF 100%)',
        'hero-wash': 'linear-gradient(135deg, #F0F7FF 0%, #F8FBFF 55%, #FFFFFF 100%)',
        'card-glow': 'linear-gradient(135deg, #DCEBFF 0%, #F0F7FF 60%, #FFFFFF 100%)',
      },
    },
  },
  plugins: [],
}
