const VALIDATION_PROVENANCE = /(?:^|[^a-z])(synthetic|validation)(?:$|[^a-z])/i;

export function isValidationRecord(
  isSynthetic: boolean | null | undefined,
  provenance: string | null | undefined,
): boolean {
  const source = provenance || '';
  const explicitlyNonSynthetic = /(?:^|[^a-z])(?:not|non)[_-]?synthetic(?:$|[^a-z])/i.test(source);
  return Boolean(isSynthetic) || (
    !explicitlyNonSynthetic && VALIDATION_PROVENANCE.test(source)
  );
}
