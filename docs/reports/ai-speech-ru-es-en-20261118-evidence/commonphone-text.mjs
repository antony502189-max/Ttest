import {parquetMetadataAsync,parquetReadObjects} from '../live-voice-review/node-tooling/package/src/index.js';
import {writeFile}from'node:fs/promises';
const revision='3635a95a34c4d20337f30499e0d9ba0be30fdae3';const sizes=[388215947,430566698,405831531,417445480];const all=[];
for(let part=0;part<4;part++){
 const name=`test-${String(part).padStart(5,'0')}-of-00004.parquet`,url=`https://huggingface.co/datasets/pklumpp/CommonPhoneDataset/resolve/${revision}/data/${name}`;let bytes=0,requests=0;
 const file={byteLength:sizes[part],async slice(start,end=sizes[part]){if(end-start>2_000_000)throw Error('RANGE_TOO_LARGE');const response=await fetch(url+'?range='+start,{headers:{Range:`bytes=${start}-${end-1}`},signal:AbortSignal.timeout(30000)});if(response.status!==206||!response.headers.get('content-range')?.startsWith(`bytes ${start}-`))throw Error('RANGE_NOT_HONORED');let a=await response.arrayBuffer();bytes+=a.byteLength;requests++;if(bytes>15_000_000||a.byteLength!==end-start)throw Error('DOWNLOAD_BOUND');return a;}};
 const meta=await parquetMetadataAsync(file);console.log({part,fields:meta.schema.map(x=>x.name),groups:meta.row_groups.length});
 const rows=await parquetReadObjects({file,metadata:meta,columns:['text','language','speaker'],includeRowIndex:true});
 const found=rows.map((r,i)=>({...r,row:i,part})).filter(r=>/\b(rent|renting|room|apartment)\b|alquil|habitaci[oó]n|квартир|снять|комнат[ауые]/iu.test(r.text));all.push(...found);
 console.log({part,rows:rows.length,bytes,requests,candidates:found.length});
}
await writeFile(new URL('commonphone-candidates.json',import.meta.url),JSON.stringify(all,null,2));console.log(JSON.stringify(all.filter(r=>/\b(I |we |Can |Could |Looking |Find )|[Nn]ecesito|[Bb]usco|[Qq]uiero|[Мм]не нуж|снять/iu.test(r.text))));
