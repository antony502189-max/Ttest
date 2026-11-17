import {parquetMetadataAsync,parquetReadObjects} from '../live-voice-review/node-tooling/package/src/index.js';
import {writeFile}from'node:fs/promises';
const revision='3635a95a34c4d20337f30499e0d9ba0be30fdae3';const files=(await(await fetch(`https://huggingface.co/api/datasets/pklumpp/CommonPhoneDataset/tree/${revision}/data?limit=100`)).json()).filter(x=>/data\/(train|dev)-/.test(x.path));const all=[];
for(let part=0;part<files.length;part++){
 const name=files[part].path.split('/').pop(),url=`https://huggingface.co/datasets/pklumpp/CommonPhoneDataset/resolve/${revision}/data/${name}`;let bytes=0,requests=0;
 const file={byteLength:files[part].size,async slice(start,end=files[part].size){if(end-start>2_000_000)throw Error('RANGE_TOO_LARGE');const response=await fetch(url+'?range='+start,{headers:{Range:`bytes=${start}-${end-1}`},signal:AbortSignal.timeout(30000)});if(response.status!==206||!response.headers.get('content-range')?.startsWith(`bytes ${start}-`))throw Error('RANGE_NOT_HONORED');let a=await response.arrayBuffer();bytes+=a.byteLength;requests++;if(bytes>15_000_000||a.byteLength!==end-start)throw Error('DOWNLOAD_BOUND');return a;}};
 const meta=await parquetMetadataAsync(file);
 const rows=await parquetReadObjects({file,metadata:meta,columns:['text','language','speaker'],includeRowIndex:true});
 const found=rows.map((r,i)=>({...r,row:i,part,parquet:name})).filter(r=>/\b(rent|renting|room|apartment)\b|alquil|habitaci[oó]n|квартир|снять|комнат[ауые]/iu.test(r.text));all.push(...found);
 console.log({part,rows:rows.length,bytes,requests,candidates:found.length});
}
await writeFile(new URL('commonphone-extra-candidates.json',import.meta.url),JSON.stringify(all,null,2));console.log(JSON.stringify(all.filter(r=>/\b(I |we |Can |Could |Looking |Find )|[Nn]ecesito|[Bb]usco|[Qq]uiero|[Мм]не нуж|снять/iu.test(r.text))));
