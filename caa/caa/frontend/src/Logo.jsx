/** The official CAA logo (public/logo.png). Always sits on a white tile so it stays readable on dark backgrounds. */
export default function Logo({ size = 24, alt = "" }) {
  return <img className="logo-img" src="/logo.png" width={size} height={size} alt={alt} decoding="async" />;
}
