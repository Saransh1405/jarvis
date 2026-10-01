type IconProps = {
  paths: string;
  className?: string;
};

export function Icon({ paths, className = "i" }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      aria-hidden
      dangerouslySetInnerHTML={{ __html: paths }}
    />
  );
}
