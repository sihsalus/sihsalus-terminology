// Fetch storage separately so API credentials and headers stay with the API.
export const signedExportDownload = async response => {
  if(response.status !== 200) return response;

  const url = response.data?.url;
  if(typeof url !== 'string' || !url) throw new Error('Missing export download URL.');

  const download = await fetch(url, { credentials: 'omit' });
  if(!download.ok) throw new Error(`Export download failed (${download.status}).`);

  return {
    status: download.status,
    data: await download.blob(),
    headers: Object.fromEntries(download.headers.entries()),
  };
};
