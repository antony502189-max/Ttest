import {asyncBufferFromFile,parquetReadObjects} from './node-tooling/package/src/node.js';
import {writeFile,readFile}from'node:fs/promises';
const manifest=[];
for(const lang of ['ru-RU','es-ES']){
 const rows=await parquetReadObjects({file:await asyncBufferFromFile(new URL(lang+'.parquet',import.meta.url)),rowStart:0,rowEnd:30,utf8:false});
 for(let i=0;i<rows.length;i++){
  const row=rows[i],data=Buffer.from(row.audio.bytes);
  // Dataset originals are canonical-ish PCM RIFF; retain complete recordings.
  if(data.toString('ascii',0,4)!=='RIFF')throw Error('not wav');
  let offset=12,rate=0,channels=0,width=0,format=0,pcm;
  while(offset+8<=data.length){const label=data.toString('ascii',offset,offset+4),size=data.readUInt32LE(offset+4);if(label==='fmt '){format=data.readUInt16LE(offset+8);channels=data.readUInt16LE(offset+10);rate=data.readUInt32LE(offset+12);width=data.readUInt16LE(offset+22)}if(label==='data')pcm=data.subarray(offset+8,offset+8+size);offset+=8+size+(size%2)}
  if(channels!==1||!((format===1&&width===16)||(format===3&&width===32)||(format===7&&width===8))){console.log({lang,i,header:data.subarray(0,90).toString('hex')});throw Error(`unexpected pcm ${format}/${channels}/${width}`)}
  const size=width/8, sample=i=>{
   if(format===7){const v=(~pcm[i])&255,magnitude=(((v&15)<<3)+132)<<((v>>4)&7);return (v&128)?132-magnitude:magnitude-132}
   return format===3?Math.max(-32768,Math.min(32767,pcm.readFloatLE(i*4)*32767)):pcm.readInt16LE(i*2)
  };
  const duration=pcm.length/(rate*size);if(duration<2||duration>14)continue;
  const count=Math.floor(pcm.length/size*16000/rate),wav=Buffer.alloc(44+2*count);wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(16000,24);wav.writeUInt32LE(32000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(2*count,40);
  for(let n=0;n<count;n++){const at=n*rate/16000,left=Math.floor(at),right=Math.min(left+1,pcm.length/size-1);wav.writeInt16LE(Math.round(sample(left)*(1-(at-left))+sample(right)*(at-left)),44+n*2)}
  const file=lang+'-'+i+'.wav';await writeFile(new URL(file,import.meta.url),wav);manifest.push({id:lang+':'+row.path,file,language:lang.slice(0,2),kind:'public-human-minds14',reference:row.transcription,source_row:i});
  if(manifest.filter(r=>r.language===lang.slice(0,2)).length===3)break;
 }
}
await writeFile(new URL('human-manifest.json',import.meta.url),JSON.stringify(manifest,null,2));console.log(manifest.map(({id,file})=>({id,file})));
