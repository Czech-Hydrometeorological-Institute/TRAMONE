#define TINY_GSM_MODEM_SIM800
#include <SoftwareSerial.h>
#include <TinyGsmClient.h>
#include <PubSubClient.h>
#include <avr/wdt.h>
#include <DS18B20.h>

#define apn "internet.t-mobile.cz" 
#define user ""
#define password ""
#define mqtt_server "broker.emqx.io"
#define mqtt_port 1883
SoftwareSerial gsmSerial(7, 8); // RX, TX
#define GSM_RST 4
#define SAMPLER_0_CTRL_1 2 // middle button
#define SAMPLER_0_CTRL_2 3 // upper button
#define SAMPLER_1_CTRL_1 5 // middle button
#define SAMPLER_1_CTRL_2 6 // upper button
#define TEMP_SENS 9
#define HEATING 10

String message = "";
const char* topic_request="TRAMONE/4A/request";
const char* topic_response="TRAMONE/4A/response";
const char* client_name="TRAMONE_CLIENT_4A";
boolean test_sampler_0;
boolean test_sampler_1;
boolean request_sampler_0=false;
boolean request_sampler_1=false;
boolean messageReceived = false;
const int num_readings=500;
float PUMP_SENSOR_0;
float PUMP_SENSOR_1;
long int last_msg_time;
boolean heating=false;
boolean main_loop=false;
boolean after_reboot=false;

TinyGsm modem(gsmSerial);
TinyGsmClient gsmClient(modem);
PubSubClient client(gsmClient);
//OneWire ds(ONE_WIRE_BUS);

void reconnect(long int starttime) {
  while (!client.connected()) {
    wdt_reset();   
    Serial.print(F("Connecting to MQTT..."));
    if (client.connect(client_name)) {
      Serial.println(F("OK"));
      client.subscribe(topic_request);
    } else {
      Serial.print(F("failed, rc="));
      Serial.print(client.state());
      Serial.println(F(" try again in 5 seconds"));
      delay(5000);
      wdt_reset(); 
    }
    if (millis()-starttime>60000) {
      Serial.println(F("Connection timeout. Reboting..."));
      while(true);
      //asm volatile ("jmp 0x0000");
    }
  }
}

void callback(char* topic_request, byte* payload, unsigned int length) {
  Serial.print(F("Message arrived ["));
  Serial.print(topic_request);
  Serial.print("] ");
  messageReceived=true;
  payload[length] = '\0'; // Přidání ukončovacího znaku
  message = (char*)payload;
  Serial.println(message);
}


void PUMP_SENSOR_read(byte pin, float &pump_sens, boolean &test_sampler)
{  
  long sum=0;
  for (byte max_i=0;max_i<10; max_i++)
  {  
    long max=0;
    for (int i=0; i<num_readings; i++)
    {
      long value=analogRead(pin);
      if (value>max)
      {
        max=value;      
      }
    }
    sum=sum+max;
    delay(50);
  }
  pump_sens=sum/10;
  wdt_reset(); 

  if (pump_sens>700) 
  {
    test_sampler=true;
  }
  else if (pump_sens<600) 
  {
    test_sampler=false;
  }

}


void sampler_start(byte CTRL_1,byte CTRL_2)
{
      digitalWrite(CTRL_1, LOW);
      delay(250);
      digitalWrite(CTRL_1, HIGH);
      delay(3000);
      wdt_reset();
      digitalWrite(CTRL_1, LOW);
      delay(250);
      digitalWrite(CTRL_1, HIGH);
      delay(3000);
      wdt_reset();
      digitalWrite(CTRL_2, LOW);
      delay(250);
      digitalWrite(CTRL_2, HIGH);
      delay(1000);
      digitalWrite(CTRL_1, LOW);
      delay(250);
      digitalWrite(CTRL_1, HIGH);
      delay(4000);
      wdt_reset();
      digitalWrite(CTRL_1, LOW);
      delay(250);
      digitalWrite(CTRL_1, HIGH);
      delay(1000); 
      wdt_reset();  
}

void sampler_stop(byte CTRL_1)
{
      digitalWrite(CTRL_1, LOW);
      wdt_reset();
      delay(5000);
      wdt_reset();
      delay(5000);
      wdt_reset();
      digitalWrite(CTRL_1, HIGH);
      delay(1000);
      wdt_reset();
}


void temp_and_heat() {
  DS18B20 ds(TEMP_SENS);
  float temp[2];
  int count_sens=0;
  while (ds.selectNext()) {
    temp[count_sens]=ds.getTempC();
    count_sens++;
    if (count_sens==2) {
      break;
    }
    wdt_reset();
  }
  Serial.print(F("Temp out: "));
  Serial.print(temp[0]);
  Serial.println(F(" °C"));
  Serial.print(F("Temp in: "));
  Serial.print(temp[1]);
  Serial.println(F(" °C"));

  if (main_loop=true) {
    client.publish(topic_response, reinterpret_cast<const uint8_t*>(("TEMP|"+String(temp[0], 2)+"|"+String(temp[1], 2)+"     ").c_str()),18,false);
    wdt_reset();
  }

  // heating controll with hysteresis
  if ( (temp[0]<25 && (temp[0]-temp[1])<2)  || temp[0]<5 ) {
    //heating start
    digitalWrite(HEATING, HIGH); //aktivní v HIGH
    if (heating==false && main_loop==true) {
      client.publish(topic_response, reinterpret_cast<const uint8_t*>("HEAT|ON|OK"),10,false);
      wdt_reset();
    }
    heating=true;
  }
  if ( (temp[0]>7 && (temp[0]-temp[1])>2.5) || temp[0]>27 ) {
    //heating stop
    digitalWrite(HEATING, LOW);
    if (heating==true && main_loop==true) {
      client.publish(topic_response, reinterpret_cast<const uint8_t*>("HEAT|OFF|OK"),11,false);
      wdt_reset();
    }
    heating=false;
  }
}


void setup() {

  wdt_enable(WDTO_8S);

  //init controll pins of sampler 0
  pinMode(SAMPLER_0_CTRL_1, OUTPUT);
  pinMode(SAMPLER_0_CTRL_2, OUTPUT);
  digitalWrite(SAMPLER_0_CTRL_1, HIGH);
  digitalWrite(SAMPLER_0_CTRL_2, HIGH);

  //init controll pins of sampler 1
  pinMode(SAMPLER_1_CTRL_1, OUTPUT);
  pinMode(SAMPLER_1_CTRL_2, OUTPUT);
  digitalWrite(SAMPLER_1_CTRL_1, HIGH);
  digitalWrite(SAMPLER_1_CTRL_2, HIGH);

  //init input pins of sampler 0 an sampler 1 Pump sensors
  pinMode(A0, INPUT);
  pinMode(A1, INPUT);

  //init heating pin
  pinMode(HEATING, OUTPUT);
  digitalWrite(HEATING, LOW);  

  Serial.begin(9600);

  wdt_reset(); 
  //reset GSM
  pinMode(GSM_RST, OUTPUT);
  digitalWrite(GSM_RST, LOW);
  delay(1500);
  digitalWrite(GSM_RST, HIGH);
  delay(2000);
  gsmSerial.begin(9600);
  delay(1000);
  wdt_reset(); 
  gsmSerial.println("AT");
  delay(500);
  String gsm_message="";
  while (gsmSerial.available()) {
    char c = gsmSerial.read();
    gsm_message += c;
  }
  Serial.println(gsm_message);
  
  // Připojení k síti
  long int starttime=millis();
  Serial.print(F("Connecting to network..."));
  while (!modem.waitForNetwork()) {
    temp_and_heat();
    if (millis()-starttime>30000) {
      while (true);
      }
    else {
      wdt_reset();
    }    
  }
  Serial.println(F("OK"));

  // Připojení k GPRS
  Serial.print(F("Connecting to GPRS..."));
  starttime=millis();
  wdt_reset();
  while (!modem.gprsConnect(apn, user, password)) {
    temp_and_heat();
    if (millis()-starttime>10000) {
      while (true);
    }
    else {
      wdt_reset();
    }
  }
  Serial.println(F("OK"));

  // Nastavení MQTT serveru a callback funkce
  client.setServer(mqtt_server, mqtt_port);
  wdt_reset(); 
  client.setCallback(callback);
  client.setKeepAlive(60);
  client.loop(); 
  wdt_reset(); 
  delay(500);
  wdt_reset(); 
  after_reboot=true;
  last_msg_time=millis();
}
// end setup()


  


void loop() {
 main_loop=true;
 client.loop();
 wdt_reset();
 if (!modem.isNetworkConnected()) {
    while(true);
    //asm volatile ("jmp 0x0000")
  }
  client.loop();
  wdt_reset();
  delay(100);
  if (!client.connected()) {
    long int starttime=millis();
    reconnect(starttime);
    wdt_reset();
  }  
  client.loop(); 
  if (after_reboot)
  {
    client.publish(topic_response, reinterpret_cast<const uint8_t*>("STATE|REBOOT|OK"),15,false);
    client.loop(); 
    after_reboot=false;
  }
  if (messageReceived)
  {
    last_msg_time=millis();
  }
  if (messageReceived && message!="99")
  {
    // char to boolean for evaluating conditions
    request_sampler_0 = (message.charAt(0) == '1');
    request_sampler_1 = (message.charAt(1) == '1');
    Serial.println(F("A new request detected"));
    Serial.println("ACCEPT|"+message);
    client.publish(topic_response, reinterpret_cast<const uint8_t*>(("ACCEPT|"+message+"|OK").c_str()),12 , false);
    client.loop();
    messageReceived=false;
    wdt_reset(); 
  }

  if (millis()-last_msg_time>360000)
  {
    //connection error, reboot by watchdog
    while(true);
  }

// ***************************
// sampler pump operation read
  PUMP_SENSOR_read(A0,PUMP_SENSOR_0,test_sampler_0);
  PUMP_SENSOR_read(A1,PUMP_SENSOR_1,test_sampler_1);
  Serial.print("PUMP_SENSOR_0: ");
  Serial.println(PUMP_SENSOR_0);
  Serial.print("PUMP_SENSOR_1: ");
  Serial.println(PUMP_SENSOR_1);
  client.publish(topic_response, reinterpret_cast<const uint8_t*>(("PUMP|"+String(PUMP_SENSOR_0, 0)+"|"+String(PUMP_SENSOR_1, 0)+"     ").c_str()),15,false);
  client.loop();
  wdt_reset();
// end sampler pump operation test
// *******************************
 
  //startovací sekvence pro sampler 0:
  if ((request_sampler_0 == true) && (test_sampler_0==false))
  {
    client.publish(topic_response, reinterpret_cast<const uint8_t*>("EXEC|0|ON"),9, false);
    client.loop();
    Serial.println(F("Sampler 0 switching on..."));
    sampler_start(SAMPLER_0_CTRL_1,SAMPLER_0_CTRL_2);
    Serial.println(F("Sampler switching on finished"));
    wdt_reset(); 
  }
  //vypínací sekvence pro sampler 0:
  if ((request_sampler_0 == false) && (test_sampler_0==true))
  {
    client.publish(topic_response,  reinterpret_cast<const uint8_t*>("EXEC|0|OFF"),10, false);
    client.loop();
    Serial.println(F("Sampler switching off..."));
    sampler_stop(SAMPLER_0_CTRL_1);
    Serial.println(F("Sampler switching off finished"));
    wdt_reset(); 
  }
  //startovací sekvence pro sampler 1:
  if ((request_sampler_1==true) && (test_sampler_1==false) )
  {
    client.publish(topic_response, reinterpret_cast<const uint8_t*>("EXEC|1|ON"),9, false);
    client.loop();
    Serial.println(F("Sampler 1 switching on..."));
    sampler_start(SAMPLER_1_CTRL_1,SAMPLER_1_CTRL_2);
    Serial.println(F("Sampler switching on finished"));
    wdt_reset(); 
  }
  //vypínací sekvence pro sampler 1:
  if ((request_sampler_1==false) && (test_sampler_1==true))
  {
    client.publish(topic_response, reinterpret_cast<const uint8_t*>("EXEC|1|OFF"),10, false);
    client.loop();
    Serial.println(F("Sampler switching off..."));
    sampler_stop(SAMPLER_1_CTRL_1);
    Serial.println(F("Sampler switching off finished"));
    wdt_reset(); 
  }
  PUMP_SENSOR_read(A0,PUMP_SENSOR_0,test_sampler_0);
  PUMP_SENSOR_read(A1,PUMP_SENSOR_1,test_sampler_1);  
  String response_sampler0 = test_sampler_0 ? "1" : "0"; 
  String response_sampler1 = test_sampler_1 ? "1" : "0";   
  if ((request_sampler_0 == test_sampler_0) && (request_sampler_1 == test_sampler_1))
  {  
    client.publish(topic_response, reinterpret_cast<const uint8_t*>(("STATE|"+response_sampler0+response_sampler1+"|OK").c_str()), 11, false);
    client.loop();
    Serial.println("STATE_"+response_sampler0+response_sampler1);
    wdt_reset(); 
  }
  else
  {
    client.publish(topic_response, reinterpret_cast<const uint8_t*>(("STATE|"+response_sampler0+response_sampler1+"|ERROR").c_str()), 14, false);
    client.loop();
    Serial.println("STATE_"+response_sampler0+response_sampler1);
    wdt_reset(); 
  }
  temp_and_heat();
  client.loop();
  wdt_reset(); 
  delay(4000);
  client.loop();
  wdt_reset();
  delay(4000);
  wdt_reset();
 
}
