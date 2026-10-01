// Arduino DUE, protocol V2. Original DMS283 pin assignments preserved.
// Commands: id HELLO | PING | STATUS | OFF 0/1/2 | ROUTE channel bypass well
#include <Arduino.h>
#include <string.h>
#include <stdlib.h>

const uint8_t enablePins[2][2] = {{26,30},{28,32}};
const uint8_t addressPins[2][2][4] = {{{23,25,27,29},{31,33,35,255}},{{37,39,41,43},{45,47,49,255}}};
const uint8_t bypassPins[2] = {22,24};
char wells[2][3] = {"-","-"};
uint8_t bypassState[2] = {1,1};
char buffer[96]; size_t used = 0; bool overflowed = false;
bool alive = false; unsigned long heartbeatAt = 0;

void off(int ch) {
  digitalWrite(enablePins[ch][0],LOW); digitalWrite(enablePins[ch][1],LOW);
  strcpy(wells[ch],"-");
}
bool validWell(const char *s) {
  return strlen(s)==2 && s[0]>='A' && s[0]<='D' && s[1]>='1' && s[1]<='6';
}
void reply(const char *id,const char *kind,const char *message) {
  Serial.print(id); Serial.print(' '); Serial.print(kind); Serial.print(' '); Serial.println(message);
}
void command(char *line) {
  char *tokens[7]; int count=0; char *save;
  for(char *p=strtok_r(line," \r",&save);p && count<7;p=strtok_r(NULL," \r",&save)) tokens[count++]=p;
  if(count<2) { reply("0","ERR","FORMAT"); return; }
  const char *id=tokens[0];
  if(strlen(id)>10) {reply("0","ERR","ID");return;}
  for(size_t i=0;i<strlen(id);i++) if(id[i]<'0'||id[i]>'9') {reply("0","ERR","ID");return;}
  const char *op=tokens[1];
  if(count==2 && !strcmp(op,"HELLO")) {reply(id,"OK","V2");return;}
  if(count==2 && !strcmp(op,"PING")) {alive=true;heartbeatAt=millis();reply(id,"OK","PONG");return;}
  if(count==2 && !strcmp(op,"STATUS")) {
    char result[48];snprintf(result,sizeof(result),"STATE %s %u %s %u",wells[0],bypassState[0],wells[1],bypassState[1]);
    reply(id,"OK",result);return;
  }
  if(count==3 && !strcmp(op,"OFF") && strlen(tokens[2])==1 && tokens[2][0]>='0' && tokens[2][0]<='2') {
    int ch=tokens[2][0]-'0';if(ch==0){off(0);off(1);}else off(ch-1);
    char result[12];snprintf(result,sizeof(result),"OFF %d",ch);reply(id,"OK",result);return;
  }
  if(count!=5 || strcmp(op,"ROUTE") || strlen(tokens[2])!=1 || (tokens[2][0]!='1'&&tokens[2][0]!='2') ||
     strlen(tokens[3])!=1 || (tokens[3][0]!='0'&&tokens[3][0]!='1') || !validWell(tokens[4])) {reply(id,"ERR","INVALID_COMMAND");return;}
  if(!alive) {reply(id,"ERR","HEARTBEAT_REQUIRED");return;}
  int ch=tokens[2][0]-'1',bp=tokens[3][0]-'0';const char *well=tokens[4];
  if(!strcmp(wells[1-ch],well)) {reply(id,"ERR","WELL_CONFLICT");return;}
  off(ch); // Both banks disabled before changing any address or filter pin.
  digitalWrite(bypassPins[ch],bp==1?LOW:HIGH);bypassState[ch]=bp;
  int col=well[1]-'1', row=well[0]-'A',bank=col<4?0:1;
  int addr=row+4*(bank==0?col:col-4);
  for(int b=0;b<2;b++) for(int bit=0;bit<(b==0?4:3);bit++)
    digitalWrite(addressPins[ch][b][bit],b==bank && (addr&(1<<bit))?HIGH:LOW);
  delayMicroseconds(10);
  digitalWrite(enablePins[ch][bank],HIGH);strcpy(wells[ch],well);
  char result[32];snprintf(result,sizeof(result),"ROUTE %d %d %s",ch+1,bp,well);reply(id,"OK",result);
}
void setup() {
  for(int ch=0;ch<2;ch++) {
    for(int bank=0;bank<2;bank++) {
      digitalWrite(enablePins[ch][bank],LOW);pinMode(enablePins[ch][bank],OUTPUT);
      for(int bit=0;bit<(bank==0?4:3);bit++) {digitalWrite(addressPins[ch][bank][bit],LOW);pinMode(addressPins[ch][bank][bit],OUTPUT);}
    }
    digitalWrite(bypassPins[ch],LOW);pinMode(bypassPins[ch],OUTPUT);off(ch);
  }
  Serial.begin(9600);Serial.println("BOOT V2 DISCONNECTED");
}
void loop() {
  if(alive && (unsigned long)(millis()-heartbeatAt)>=5000) {
    off(0);off(1);alive=false;Serial.println("0 ERR WATCHDOG");
  }
  // Bound work per loop so a stream without a terminator cannot starve the watchdog.
  for(int processed=0;processed<32 && Serial.available();processed++) {
    char c=Serial.read();
    if(c=='\n') {
      if(overflowed) reply("0","ERR","LINE_TOO_LONG");
      else {buffer[used]=0;command(buffer);}
      used=0;overflowed=false;
    } else if(!overflowed) {
      if(c==0 || used>=sizeof(buffer)-1) overflowed=true;
      else buffer[used++]=c;
    }
  }
}
