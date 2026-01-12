/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                fraunces: ['Fraunces', 'serif'],
                nunito: ['Nunito', 'sans-serif'],
            },
            colors: {
                organic: {
                    primary: '#5D7052',
                    secondary: '#C18C5D',
                    bg: '#FDFCF8',
                    text: '#2C2C24',
                    accent: '#A85448',
                    light: '#DED8CF',
                }
            },
            animation: {
                'spin-slow': 'spin 3s linear infinite',
            },
            keyframes: {
                spin: {
                    from: { transform: 'rotate(0deg)' },
                    to: { transform: 'rotate(360deg)' },
                }
            }
        },
    },
    plugins: [],
}
