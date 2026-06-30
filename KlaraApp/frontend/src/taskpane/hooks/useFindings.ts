import { useQuery } from '@tanstack/react-query';
import { qcApi } from '../api/qc';
import type { QCFinding } from '../types';

export function useFindings(docId: string | null) {
  return useQuery({
    queryKey: ['findings', docId],
    queryFn: async () => {
      if (!docId) return [] as QCFinding[];
      return await qcApi.getFindings(docId);
    },
    enabled: !!docId, // Only fetch when we have a docId
  });
}
